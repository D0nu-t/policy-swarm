"""
policyswarm.experiments.params
==============================
Declarative descriptions of the parameters an experiment accepts.

Each experiment class lists its sweepable constructor arguments as a tuple of
``ParamSpec`` objects (``PARAMS``). The same declaration serves three
consumers:

  * the registry, to validate and coerce a JSON run description into
    constructor keyword arguments (``ParamSpec.parse``);
  * the CLI, to accept a ``--spec`` file;
  * the dashboard, to render an input form (``ParamSpec.to_dict``).

Values travel as plain JSON: enum members are represented by their ``value``
string and converted back to the enum on ``parse``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Type

_SCALAR_KINDS = ("int", "float", "bool", "choice")


class ParamError(ValueError):
    """A supplied parameter value is missing, mistyped or out of range."""


@dataclass(frozen=True)
class ParamSpec:
    """One experiment parameter.

    Parameters
    ----------
    name : str
        Constructor keyword argument name.
    kind : {"int", "float", "bool", "choice"}
        Element type.
    default : Any
        JSON-friendly default (enum members as their ``value``).
    many : bool
        True if the parameter is a list of ``kind`` (a sweep axis).
    choices : tuple of str, optional
        Allowed values for ``kind="choice"``. Derived from ``enum`` if given.
    enum : Enum subclass, optional
        If set, parsed choice strings are converted to this enum.
    optional : bool
        True if ``None`` is an accepted scalar value.
    minimum, maximum : float, optional
        Inclusive bounds for numeric kinds.
    help : str
        One-line description shown in the CLI and dashboard.
    label : str
        Human-readable name for forms (default: the dashboard humanises ``name``).
    group : str
        Form section the field belongs to (dashboard only).
    """

    name     : str
    kind     : str
    default  : Any
    many     : bool                      = False
    choices  : Optional[Tuple[str, ...]] = None
    enum     : Optional[Type[Enum]]      = None
    optional : bool                      = False
    minimum  : Optional[float]           = None
    maximum  : Optional[float]           = None
    help     : str                       = ""
    label    : str                       = ""
    group    : str                       = ""

    def __post_init__(self) -> None:
        if self.kind not in _SCALAR_KINDS:
            raise ValueError(f"Unknown ParamSpec kind: {self.kind!r}")
        if self.enum is not None and self.choices is None:
            object.__setattr__(self, "choices", tuple(m.value for m in self.enum))
        if self.kind == "choice" and not self.choices:
            raise ValueError(f"ParamSpec {self.name!r}: 'choice' needs choices or enum")

    # ------------------------------------------------------------------
    # Validation / coercion
    # ------------------------------------------------------------------

    def parse(self, raw: Any) -> Any:
        """Validate a JSON value and return the constructor argument."""
        if self.many:
            if not isinstance(raw, (list, tuple)) or len(raw) == 0:
                raise ParamError(f"{self.name}: expected a non-empty list")
            return [self._parse_scalar(v) for v in raw]
        if raw is None:
            if self.optional:
                return None
            raise ParamError(f"{self.name}: a value is required")
        return self._parse_scalar(raw)

    def _parse_scalar(self, value: Any) -> Any:
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise ParamError(f"{self.name}: expected true/false, got {value!r}")
            return value

        if self.kind == "choice":
            if value not in self.choices:
                raise ParamError(
                    f"{self.name}: {value!r} is not one of {list(self.choices)}"
                )
            return self.enum(value) if self.enum is not None else value

        # bool is a subclass of int; reject it explicitly for numeric kinds
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ParamError(f"{self.name}: expected a number, got {value!r}")
        if self.kind == "int":
            if float(value) != int(value):
                raise ParamError(f"{self.name}: expected an integer, got {value!r}")
            value = int(value)
        else:
            value = float(value)
        if self.minimum is not None and value < self.minimum:
            raise ParamError(f"{self.name}: {value} is below the minimum {self.minimum}")
        if self.maximum is not None and value > self.maximum:
            raise ParamError(f"{self.name}: {value} is above the maximum {self.maximum}")
        return value

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable description (used by the dashboard form)."""
        return {
            "name"    : self.name,
            "kind"    : self.kind,
            "default" : self.default,
            "many"    : self.many,
            "choices" : list(self.choices) if self.choices else None,
            "optional": self.optional,
            "minimum" : self.minimum,
            "maximum" : self.maximum,
            "help"    : self.help,
            "label"   : self.label,
            "group"   : self.group,
        }


def parse_params(specs: Tuple[ParamSpec, ...], raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate a ``{name: json_value}`` mapping against ``specs``.

    Only supplied keys are returned, so omitted parameters keep the
    experiment's own constructor defaults. Unknown keys are an error.
    """
    raw = raw or {}
    by_name = {s.name: s for s in specs}
    unknown = sorted(set(raw) - set(by_name))
    if unknown:
        raise ParamError(f"Unknown parameter(s): {unknown}. Allowed: {sorted(by_name)}")
    return {name: by_name[name].parse(value) for name, value in raw.items()}


def specs_from_dataclass(cls: type, help_text: Optional[Dict[str, str]] = None) -> Tuple[ParamSpec, ...]:
    """Derive ParamSpecs from the int / float / bool / Enum fields of a config dataclass."""
    help_text = help_text or {}
    specs = []
    for f in dataclasses.fields(cls):
        default = f.default
        if isinstance(default, Enum):
            specs.append(ParamSpec(f.name, "choice", default.value, enum=type(default),
                                   help=help_text.get(f.name, "")))
        elif isinstance(default, bool):
            specs.append(ParamSpec(f.name, "bool", default, help=help_text.get(f.name, "")))
        elif isinstance(default, int):
            specs.append(ParamSpec(f.name, "int", default, minimum=0,
                                   help=help_text.get(f.name, "")))
        elif isinstance(default, float):
            specs.append(ParamSpec(f.name, "float", default, minimum=0.0,
                                   help=help_text.get(f.name, "")))
    return tuple(specs)
