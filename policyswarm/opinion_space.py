"""
policyswarm.opinion_space
=========================
A user-defined opinion space: what the dimensions are, where the policy sits
on them, and which words in a policy text move which dimension.

By default PolicySwarm runs on four fixed AI-governance dimensions, with a
built-in keyword table (``extraction._KEYWORD_MAP``). An ``OpinionSpace``
replaces all three pieces with data, so they can be set from a run file
(``RunSpec.opinion_space``) or the dashboard:

    space = OpinionSpace.from_dict({
        "dimensions": [
            {"name": "openness", "ideology_sensitivity": -0.2},
            {"name": "oversight", "ideology_sensitivity": 0.3, "tightening": 0.2},
        ],
        "violator_dimension": "openness",
        "violator_threshold": 0.6,
        "position": {"openness": -0.4, "oversight": 0.7},
    })
    policy = space.build_policy(policy_text)      # a generic N-dimension Policy

Units
-----
Every value here is on the simulation's own scale: -1 to 1, with 0 neutral.
That covers positions, the violator threshold, keyword deltas and tightening.
(The built-in keyword table and schema YAMLs are written on the unit interval;
they are converted when loaded, see ``default`` and ``from_schema_yaml``.)

What the engine reads from which dimension
------------------------------------------
* ``violator_dimension``: an agent above ``violator_threshold`` on it has its
  influence penalised once enforcement starts.
* The first dimension: the Bifurcation Index and the Experiment 5 density
  figure are computed on it.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .config import CENTRED_SCALE, DEFAULT_SPLIT_DELTAS, Policy, unit_to_centred
from .experiments.params import ParamError
from .extraction import (
    DEFAULT_DIMENSIONS, DEFAULT_KEYWORD_MAP, extract_entities, extract_narrative_scores,
    keyword_positions,
)

MIN_DIMENSIONS, MAX_DIMENSIONS = 2, 12
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
SCHEMA_DIR = Path(__file__).parent / "schemas"

_DEFAULT_DESCRIPTIONS = {
    "deployment_cap" : "How freely AI systems may be deployed. Positive = permissive, "
                       "negative = restricted.",
    "transparency"   : "Disclosure and explainability requirements. Positive = strict.",
    "enforcement"    : "Strength of penalties and compliance mechanisms. Positive = strict.",
    "audit_intensity": "Depth and frequency of monitoring and audits. Positive = intensive.",
}
#: (positive end, negative end) of each built-in dimension.
_DEFAULT_ENDS = {
    "deployment_cap" : ("deployment is permissive: few limits on releasing and using AI systems",
                        "deployment is restricted: bans, licences and approvals before release"),
    "transparency"   : ("strict disclosure and explainability duties",
                        "little or no duty to disclose; secrecy is allowed"),
    "enforcement"    : ("strong penalties and powers to compel compliance",
                        "weak, delayed or no penalties"),
    "audit_intensity": ("frequent, independent audits and monitoring",
                        "little checking; providers assess themselves"),
}
_DEFAULT_SENSITIVITY = {"deployment_cap": -0.3, "transparency": 0.1,
                        "enforcement": 0.2, "audit_intensity": 0.15}


@dataclass
class Dimension:
    """One axis of the opinion space.

    Parameters
    ----------
    name : str
        Identifier (lowercase letters, digits, underscores).
    description : str
        What positive and negative values mean. Documentation only.
    ideology_sensitivity : float
        How far an agent's ideology shifts its reading of the policy on this
        dimension. Positive: pro-regulation agents perceive it as stricter.
    tightening : float
        How far the policy moves on this dimension at
        ``SimConfig.policy_split_tick``. 0 = it does not move.
    positive_means, negative_means : str
        What the positive and the negative end of the dimension stand for,
        in a few words. Documentation for people; the keyword-suggestion
        model can be shown them (``suggest.rate_keywords(use_ends=True)``)
        but is not by default. Not used by the simulation.
    """
    name                 : str
    description          : str   = ""
    ideology_sensitivity : float = 0.0
    tightening           : float = 0.0
    positive_means       : str   = ""
    negative_means       : str   = ""

    def to_dict(self) -> Dict[str, Any]:
        """JSON form. The two end descriptions are left out when empty, so
        spaces written before they existed round-trip unchanged."""
        data = asdict(self)
        for key in ("positive_means", "negative_means"):
            if not data[key]:
                del data[key]
        return data


@dataclass
class KeywordRule:
    """A word or phrase in the policy text that moves one dimension by ``delta``."""
    keyword   : str
    dimension : str
    delta     : float


@dataclass
class OpinionSpace:
    """A complete opinion-space definition.

    Parameters
    ----------
    dimensions : list of Dimension
        Between 2 and 12 (the angular geometries need at least two).
    violator_dimension : str
        Name of the dimension used for violator detection.
    violator_threshold : float
    keywords : list of KeywordRule
        Used to derive the policy position from the policy text.
    position : dict of str -> float, optional
        The policy's position on every dimension, set by hand. None = derive
        it from the policy text with ``keywords``.
    """
    dimensions         : List[Dimension]
    violator_dimension : str
    violator_threshold : float                      = 0.6
    keywords           : List[KeywordRule]          = field(default_factory=list)
    position           : Optional[Dict[str, float]] = None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "OpinionSpace":
        """The built-in AI-governance space, expressed as data.

        ``default().build_policy(text)`` equals ``extraction.policy_from_text(text)``.
        """
        return cls(
            dimensions=[
                Dimension(name, _DEFAULT_DESCRIPTIONS[name], _DEFAULT_SENSITIVITY[name],
                          DEFAULT_SPLIT_DELTAS.get(name, 0.0), *_DEFAULT_ENDS[name])
                for name in DEFAULT_DIMENSIONS
            ],
            violator_dimension=DEFAULT_DIMENSIONS[0],
            violator_threshold=Policy().violator_threshold,
            keywords=[KeywordRule(keyword, dimension, CENTRED_SCALE * delta)
                      for keyword, (dimension, delta) in DEFAULT_KEYWORD_MAP.items()],
        )

    @classmethod
    def from_schema_yaml(cls, path) -> "OpinionSpace":
        """Build a space from a policy schema YAML (the format of ``schemas/``).

        Schemas carry no keyword rules, so the position starts neutral and is
        meant to be set by hand.
        """
        from .extraction_llm import PolicySchema

        schema = PolicySchema.from_yaml(path)
        return cls(
            dimensions=[Dimension(d.name, " ".join(d.description.split()),
                                  d.ideology_sensitivity) for d in schema.dimensions],
            violator_dimension=schema.violator_dimension,
            violator_threshold=unit_to_centred(schema.violator_threshold),
            position={d.name: 0.0 for d in schema.dimensions},
        )

    @classmethod
    def from_dict(cls, data: Any) -> "OpinionSpace":
        """Parse and validate a JSON-level description. Raises ``ParamError``."""
        if not isinstance(data, dict):
            raise ParamError("opinion_space: expected an object")
        _check_keys("opinion_space", data,
                    required={"dimensions", "violator_dimension"},
                    optional={"violator_threshold", "keywords", "position"})
        if not isinstance(data["dimensions"], list):
            raise ParamError("opinion_space.dimensions: expected a list")
        dimensions = []
        for i, raw in enumerate(data["dimensions"]):
            where = f"opinion_space.dimensions[{i}]"
            if not isinstance(raw, dict):
                raise ParamError(f"{where}: expected an object")
            _check_keys(where, raw, required={"name"},
                        optional={"description", "ideology_sensitivity", "tightening",
                                  "positive_means", "negative_means"})
            dimensions.append(Dimension(
                name=_string(raw["name"], f"{where}.name"),
                description=_string(raw.get("description", ""), f"{where}.description"),
                ideology_sensitivity=_number(raw.get("ideology_sensitivity", 0.0),
                                             f"{where}.ideology_sensitivity"),
                tightening=_number(raw.get("tightening", 0.0), f"{where}.tightening"),
                positive_means=_string(raw.get("positive_means", ""), f"{where}.positive_means"),
                negative_means=_string(raw.get("negative_means", ""), f"{where}.negative_means"),
            ))

        raw_keywords = data.get("keywords") or []
        if not isinstance(raw_keywords, list):
            raise ParamError("opinion_space.keywords: expected a list")
        keywords = []
        for i, raw in enumerate(raw_keywords):
            where = f"opinion_space.keywords[{i}]"
            if not isinstance(raw, dict):
                raise ParamError(f"{where}: expected an object")
            _check_keys(where, raw, required={"keyword", "dimension", "delta"}, optional=set())
            keywords.append(KeywordRule(
                keyword=_string(raw["keyword"], f"{where}.keyword").strip().lower(),
                dimension=_string(raw["dimension"], f"{where}.dimension"),
                delta=_number(raw["delta"], f"{where}.delta"),
            ))

        position = data.get("position")
        if position is not None:
            if not isinstance(position, dict):
                raise ParamError("opinion_space.position: expected an object or null")
            position = {_string(k, "opinion_space.position"):
                        _number(v, f"opinion_space.position.{k}") for k, v in position.items()}

        space = cls(
            dimensions=dimensions,
            violator_dimension=_string(data["violator_dimension"],
                                       "opinion_space.violator_dimension"),
            violator_threshold=_number(data.get("violator_threshold", 0.6),
                                       "opinion_space.violator_threshold"),
            keywords=keywords,
            position=position,
        )
        space.validate()
        return space

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "dimensions": [d.to_dict() for d in self.dimensions]}

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @property
    def dimension_names(self) -> List[str]:
        return [d.name for d in self.dimensions]

    def validate(self) -> None:
        """Raise ``ParamError`` describing the first problem found."""
        names = self.dimension_names
        if not MIN_DIMENSIONS <= len(names) <= MAX_DIMENSIONS:
            raise ParamError(
                f"opinion_space: needs {MIN_DIMENSIONS}-{MAX_DIMENSIONS} dimensions, got {len(names)}"
            )
        for name in names:
            if not _NAME_RE.match(name):
                raise ParamError(
                    f"opinion_space: dimension name {name!r} must start with a letter and "
                    "use only lowercase letters, digits and underscores"
                )
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ParamError(f"opinion_space: duplicate dimension name(s): {duplicates}")

        for d in self.dimensions:
            _in_range(d.ideology_sensitivity, -1, 1, f"{d.name}.ideology_sensitivity")
            _in_range(d.tightening, -2, 2, f"{d.name}.tightening")
        if self.violator_dimension not in names:
            raise ParamError(
                f"opinion_space: violator_dimension {self.violator_dimension!r} is not a dimension"
            )
        _in_range(self.violator_threshold, -1, 1, "violator_threshold")

        seen = set()
        for rule in self.keywords:
            if not rule.keyword or len(rule.keyword) > 60:
                raise ParamError("opinion_space: keywords must be 1-60 characters")
            if rule.keyword in seen:
                raise ParamError(f"opinion_space: keyword {rule.keyword!r} appears twice")
            seen.add(rule.keyword)
            if rule.dimension not in names:
                raise ParamError(
                    f"opinion_space: keyword {rule.keyword!r} targets unknown dimension "
                    f"{rule.dimension!r}"
                )
            _in_range(rule.delta, -2, 2, f"keyword {rule.keyword!r} delta")

        if self.position is not None:
            if set(self.position) != set(names):
                raise ParamError(
                    "opinion_space: position must give a value for every dimension and no "
                    f"others (dimensions: {names})"
                )
            for name, value in self.position.items():
                _in_range(value, -1, 1, f"position.{name}")

    # ------------------------------------------------------------------
    # Policy construction
    # ------------------------------------------------------------------

    def _keyword_map(self) -> Dict[str, tuple]:
        """Rules in the extractor's native form: unit-interval deltas."""
        return {r.keyword: (r.dimension, r.delta / CENTRED_SCALE) for r in self.keywords}

    def matched_keywords(self, policy_text: str) -> List[str]:
        """The rule keywords that occur in ``policy_text`` (sorted)."""
        keyword_map = self._keyword_map()
        return [e for e in extract_entities(policy_text, keyword_map) if e in keyword_map]

    def policy_position(self, policy_text: str) -> Dict[str, float]:
        """The policy's position per dimension: hand-set, or derived from the text."""
        if self.position is not None:
            return {name: float(self.position[name]) for name in self.dimension_names}
        keyword_map = self._keyword_map()
        unit = keyword_positions(
            extract_entities(policy_text, keyword_map), keyword_map, self.dimension_names
        )
        return {name: unit_to_centred(unit[name]) for name in self.dimension_names}

    def build_policy(self, policy_text: str, lag: int = 10) -> Policy:
        """Construct the generic N-dimension ``Policy`` this space describes."""
        self.validate()
        position = self.policy_position(policy_text)
        names = self.dimension_names
        return Policy(
            vector             = np.array([position[n] for n in names], dtype=float),
            dimension_names    = names,
            dimension_salience = np.array([d.ideology_sensitivity for d in self.dimensions]),
            violator_dim_index = names.index(self.violator_dimension),
            violator_threshold = float(self.violator_threshold),
            split_deltas       = {d.name: float(d.tightening)
                                  for d in self.dimensions if d.tightening != 0},
            lag                = lag,
            narrative          = extract_narrative_scores(policy_text),
        )


def presets() -> Dict[str, OpinionSpace]:
    """Named starting points offered by the dashboard."""
    return {
        "AI governance (default)": OpinionSpace.default(),
        "Healthcare": OpinionSpace.from_schema_yaml(SCHEMA_DIR / "healthcare_policy.yaml"),
    }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _check_keys(where: str, data: dict, required: set, optional: set) -> None:
    missing = sorted(required - set(data))
    if missing:
        raise ParamError(f"{where}: missing {missing}")
    unknown = sorted(set(data) - required - optional)
    if unknown:
        raise ParamError(f"{where}: unknown field(s) {unknown}")


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise ParamError(f"{where}: expected text, got {value!r}")
    return value


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise ParamError(f"{where}: expected a number, got {value!r}")
    return float(value)


def _in_range(value: float, low: float, high: float, where: str) -> None:
    if not low <= value <= high:
        raise ParamError(f"opinion_space: {where} = {value} is outside [{low}, {high}]")
