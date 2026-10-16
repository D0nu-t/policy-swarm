"""
policyswarm.extraction
======================
Policy-text ingestion pipeline: NER extraction, knowledge graph construction,
and mapping from KG entities to a 4-D Policy object.

Pipeline stages
---------------
1. Text → Entities      extract_entities()
2. Entities → KG        build_kg()
3. KG → Policy object   policy_from_kg()
4. Full pipeline        policy_from_text()

spaCy is optional. When unavailable the module falls back to a keyword-match
extractor that covers all tokens used in the default POLICY_TEXT and the
design-document examples.

Ideological distortion
-----------------------
perceived_policy() now accepts dimension_salience and noise_scale as arrays,
making it generic for any N-dim policy. The legacy 4-dim AI policy default
behaviour is preserved when these parameters are omitted.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Union

import networkx as nx
import numpy as np

from .config import CENTRED_SCALE, Policy, unit_to_centred

# ---------------------------------------------------------------------------
# spaCy import guard
# ---------------------------------------------------------------------------
try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
except (ImportError, OSError):
    _NLP = None
    _SPACY_AVAILABLE = False

# ---------------------------------------------------------------------------
# Keyword ontology
# ---------------------------------------------------------------------------
_KEYWORD_MAP: Dict[str, Tuple[str, float]] = {
    "safety"         : ("enforcement",     +0.25),
    "safe"           : ("enforcement",     +0.20),
    "risk"           : ("enforcement",     +0.20),
    "secure"         : ("enforcement",     +0.15),
    "transparency"   : ("transparency",    +0.30),
    "transparent"    : ("transparency",    +0.25),
    "disclosure"     : ("transparency",    +0.20),
    "audit"          : ("audit_intensity", +0.30),
    "audits"         : ("audit_intensity", +0.30),
    "monitor"        : ("audit_intensity", +0.20),
    "innovation"     : ("deployment_cap",  +0.25),
    "deployment"     : ("deployment_cap",  -0.15),
    "deploy"         : ("deployment_cap",  -0.10),
    "restrict"       : ("deployment_cap",  -0.20),
    "limit"          : ("deployment_cap",  -0.15),
    "ban"            : ("deployment_cap",  -0.35),
    "penalties"      : ("enforcement",     +0.30),
    "penalty"        : ("enforcement",     +0.25),
    "compliance"     : ("enforcement",     +0.20),
    "non-compliance" : ("enforcement",     +0.20),
    "regulation"     : ("enforcement",     +0.15),
    "regulations"    : ("enforcement",     +0.15),
    "strict"         : ("enforcement",     +0.25),
}

#: Public name for the built-in keyword rule table (unit-interval deltas).
DEFAULT_KEYWORD_MAP = _KEYWORD_MAP

_NARRATIVE_KEYWORDS: Dict[str, List[str]] = {
    "safety"      : ["safety", "safe", "risk", "harm", "secure", "dangerous"],
    "innovation"  : ["innovation", "progress", "competitive", "economic", "growth"],
    "transparency": ["transparency", "disclosure", "audit", "accountable", "open"],
}


# ---------------------------------------------------------------------------
# Default policy text
# ---------------------------------------------------------------------------

#: The policy document used when an experiment is given no text and no
#: pre-built Policy. Every committed results CSV was produced with it.
DEFAULT_POLICY_TEXT = """
1. OBJECTIVE AND GUIDING PRINCIPLE
The government hereby establishes a comprehensive, risk-based regulatory framework for Artificial Intelligence (AI). This policy explicitly prioritizes public safety, fundamental human rights, and systemic security over unrestrained technical innovation. Where severe or irreversible risks to public welfare are identified, the absence of full scientific certainty shall not be used as a reason for postponing precautionary regulations.

2. CLASSIFICATION OF RISK TIERS
AI systems shall be categorized into distinct risk tiers, drawing direct inspiration from the European Union AI Act framework:
  * Prohibited Systems: AI practices that present an unacceptable risk to human safety and civil liberties are banned outright. This includes systems utilizing subliminal techniques to manipulate behavior, untargeted scraping of facial images for biometric surveillance, and state-backed social scoring systems.
  * High-Risk Systems: AI deployed in critical infrastructure (such as water, electricity, and transport networks), medical devices, biometric identification, law enforcement, and systemic employment or education algorithms are subject to rigorous pre-market and post-market obligations.

3. MANDATORY TRANSPARENCY AUDITS AND LIFECYCLE MANAGEMENT
Providers and deployers of High-Risk and General-Purpose AI (GPAI) models must adhere to strict transparency and technical documentation standards:
  * Conformity Assessments: Developers must perform independent or third-party conformity assessments before any high-risk system can be placed on the open market.
  * Traceability & Explainability: System architectures must maintain automated logs (audit trails) ensuring transparency. AI systems interacting directly with humans must be designed to explicitly notify users that they are interacting with an AI. Synthetic content (e.g., text, video, audio) must be digitally watermarked in a machine-readable format.
  * NIST Risk Management Alignment: Entities must implement continuous risk-mitigation frameworks detailing model architecture, dataset curation, bias testing, and human-in-the-loop oversight mechanisms that allow real-time intervention and system overrides.

4. PENALTIES FOR NON-COMPLIANCE AND ENFORCEMENT
To enforce compliance, the regulatory authority establishes a tiered, dissuasive penalty regime based on global annual turnover:
  * Tier 1 (Prohibited Practices): Violations involving banned AI applications shall face administrative fines of up to €35,000,000 or up to 7% of the offending entity's total worldwide annual turnover for the preceding financial year, whichever is higher.
  * Tier 2 (High-Risk Failures): Non-compliance with mandatory high-risk obligations, data governance gaps, or structural transparency failures shall be subject to fines of up to €15,000,000 or 3% of global annual turnover.
  * Tier 3 (Procedural & Information Violations): Supplying incorrect, incomplete, or misleading information to auditing bodies or national competent authorities during an inspection shall carry penalties of up to €7,500,000 or 1% of global annual turnover.
"""


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

#: The four dimensions of the default (AI governance) opinion space, in order.
DEFAULT_DIMENSIONS: Tuple[str, ...] = (
    "deployment_cap", "transparency", "enforcement", "audit_intensity",
)

KeywordMap = Dict[str, Tuple[str, float]]


def extract_entities(text: str, keyword_map: Optional[KeywordMap] = None) -> List[str]:
    """Extract relevant policy entities from raw text.

    ``keyword_map`` is the ``{keyword: (dimension, delta)}`` rule table to
    match against; default: the built-in AI-governance table.
    """
    keyword_map = _KEYWORD_MAP if keyword_map is None else keyword_map
    found: set = set()

    if _SPACY_AVAILABLE and _NLP is not None:
        doc = _NLP(text)
        for ent in doc.ents:
            found.add(ent.text.lower().strip())

    text_lower = text.lower()
    for kw in keyword_map:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            found.add(kw)

    return sorted(found)


def keyword_positions(
    entities        : List[str],
    keyword_map     : Optional[KeywordMap]  = None,
    dimension_names : Optional[List[str]]   = None,
) -> Dict[str, float]:
    """Accumulate keyword deltas into a policy position per dimension.

    Each dimension starts at the neutral 0.5 on the unit interval; every
    matched keyword adds its delta, clipped to [0.05, 0.95] after each step.
    Returns unit-interval values (convert with ``config.unit_to_centred``).
    """
    keyword_map = _KEYWORD_MAP if keyword_map is None else keyword_map
    dims = dict.fromkeys(dimension_names or DEFAULT_DIMENSIONS, 0.5)
    for entity in entities:
        if entity in keyword_map:
            dim, delta = keyword_map[entity]
            dims[dim] = np.clip(dims[dim] + delta, 0.05, 0.95)
    return dims


def extract_narrative_scores(text: str) -> Dict[str, float]:
    """Compute narrative framing scores for a policy text."""
    text_lower = text.lower()
    scores: Dict[str, float] = {}
    for frame, keywords in _NARRATIVE_KEYWORDS.items():
        hits = sum(
            1 for kw in keywords
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower)
        )
        scores[frame] = min(hits / len(keywords), 1.0)
    return scores


# ---------------------------------------------------------------------------
# Knowledge graph construction
# ---------------------------------------------------------------------------

def build_kg(entities: List[str]) -> nx.Graph:
    """Construct a knowledge graph from extracted entities."""
    G = nx.Graph()
    for e in entities:
        G.add_node(e, label=e)
    for i, e1 in enumerate(entities):
        for e2 in entities[i + 1:]:
            G.add_edge(e1, e2, relation="related_to")
    return G


# ---------------------------------------------------------------------------
# KG → Policy mapping
# ---------------------------------------------------------------------------

def policy_from_kg(
    entities : List[str],
    lag      : int = 10,
    text     : Optional[str] = None,
) -> Policy:
    """Map KG entities to a 4-D Policy object.

    Keyword deltas accumulate on the unit interval from a neutral 0.5 and are
    clipped to [0.05, 0.95], then converted to the centred [-1, 1] space.
    """
    dims = keyword_positions(entities)

    narrative = extract_narrative_scores(text) if text else {
        "safety": 0, "innovation": 0, "transparency": 0
    }

    return Policy(
        deployment_cap  = unit_to_centred(dims["deployment_cap"]),
        transparency    = unit_to_centred(dims["transparency"]),
        enforcement     = unit_to_centred(dims["enforcement"]),
        audit_intensity = unit_to_centred(dims["audit_intensity"]),
        lag             = lag,
        narrative       = narrative,
    )


def policy_from_text(text: str, lag: int = 10) -> Policy:
    """Convenience function: text → entities → KG → Policy."""
    entities = extract_entities(text)
    return policy_from_kg(entities, lag=lag, text=text)


# ---------------------------------------------------------------------------
# Agent-level ideological distortion of policy signal
# ---------------------------------------------------------------------------

def perceived_policy(
    policy_vector      : np.ndarray,
    ideology           : float,
    trust              : float,
    dimension_salience : Optional[np.ndarray] = None,
    noise_scale        : Union[float, np.ndarray] = 0.05,
    rng                : Optional[np.random.Generator] = None,
    anchor             : Optional[np.ndarray] = None,
    offset             : Optional[float] = None,
) -> np.ndarray:
    """
    Compute an individual agent's perception of the policy vector.

    Anti-regulation agents (ideology < 0) underweight enforcement-type
    dimensions; low-trust agents discount the policy signal globally.
    The magnitude of per-dimension distortion is governed by
    dimension_salience, which is loaded from the schema YAML (Tier 1) or
    computed from PCA loadings (Tier 2).

    Parameters
    ----------
    policy_vector : np.ndarray, shape (d,)
        Raw policy position from Policy.as_vector().
    ideology : float
        Agent ideology score in [-1, 1].
        +1 = strongly pro-regulation, -1 = strongly anti-regulation.
    trust : float
        Institutional trust in [0, 1]. Beta(2,2)-distributed.
    dimension_salience : np.ndarray, shape (d,), optional
        Per-dimension ideology sensitivity, in unit-interval units. When None,
        falls back to the legacy hardcoded AI-policy bias for 4-dim vectors,
        or zeros otherwise.
    noise_scale : float or np.ndarray, shape (d,)
        Standard deviation of perceptual noise, in unit-interval units.
        Passing an array allows per-dimension noise (used to scale by inverse
        confidence in Tier 1/2). Default 0.05 (scalar).

    Bias and noise are additive offsets specified on the unit interval, so
    both are multiplied by CENTRED_SCALE here. Trust scales the policy signal
    toward the neutral origin: a zero-trust agent perceives a neutral policy.
    rng : np.random.Generator, optional
    anchor : np.ndarray, shape (d,), optional
        The point trust shrinks the signal toward (SimConfig.trust_anchor).
        None keeps the default arithmetic exactly: shrinkage toward the
        neutral origin.
    offset : float, optional
        Added to every dimension before clipping (the "level_shift" control).

    Returns
    -------
    np.ndarray, shape (d,)
        Agent's perceived policy vector, clamped to [-1, 1].
    """
    d = len(policy_vector)

    if dimension_salience is None:
        if d == 4:
            dimension_salience = np.array([-0.3, 0.1, 0.2, 0.15])
        else:
            dimension_salience = np.zeros(d)

    bias = CENTRED_SCALE * ideology * np.asarray(dimension_salience)
    scale = CENTRED_SCALE * np.asarray(noise_scale)

    if rng is not None:
        noise = rng.normal(0.0, scale, size=d)
    else:
        noise = np.random.normal(0.0, scale, size=d)

    if anchor is None:
        perceived = trust * (policy_vector + bias) + noise
    else:
        perceived = anchor + trust * (policy_vector + bias - anchor) + noise
    if offset is not None:
        perceived = perceived + offset
    return np.clip(perceived, -1.0, 1.0)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def describe_extraction(text: str) -> str:
    """Return a human-readable summary of extraction results for a text."""
    entities = extract_entities(text)
    narrative = extract_narrative_scores(text)
    policy = policy_from_text(text)

    lines = [
        "=== KG Extraction Summary ===",
        f"Entities found ({len(entities)}): {', '.join(entities) or 'none'}",
        f"Narrative framing: { {k: f'{v:.2f}' for k, v in narrative.items()} }",
        "",
        "Derived Policy:",
        f"  deployment_cap  = {policy.deployment_cap:.3f}",
        f"  transparency    = {policy.transparency:.3f}",
        f"  enforcement     = {policy.enforcement:.3f}",
        f"  audit_intensity = {policy.audit_intensity:.3f}",
        f"  lag             = {policy.lag}",
    ]
    return "\n".join(lines)
