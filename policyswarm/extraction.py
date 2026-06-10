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

from .config import Policy

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

_NARRATIVE_KEYWORDS: Dict[str, List[str]] = {
    "safety"      : ["safety", "safe", "risk", "harm", "secure", "dangerous"],
    "innovation"  : ["innovation", "progress", "competitive", "economic", "growth"],
    "transparency": ["transparency", "disclosure", "audit", "accountable", "open"],
}


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

def extract_entities(text: str) -> List[str]:
    """Extract relevant policy entities from raw text."""
    found: set = set()

    if _SPACY_AVAILABLE and _NLP is not None:
        doc = _NLP(text)
        for ent in doc.ents:
            found.add(ent.text.lower().strip())

    text_lower = text.lower()
    for kw in _KEYWORD_MAP:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            found.add(kw)

    return sorted(found)


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
    """Map KG entities to a 4-D Policy object."""
    dims = {
        "deployment_cap" : 0.5,
        "transparency"   : 0.5,
        "enforcement"    : 0.5,
        "audit_intensity": 0.5,
    }

    for entity in entities:
        if entity in _KEYWORD_MAP:
            dim, delta = _KEYWORD_MAP[entity]
            dims[dim] = np.clip(dims[dim] + delta, 0.05, 0.95)

    narrative = extract_narrative_scores(text) if text else {
        "safety": 0.5, "innovation": 0.5, "transparency": 0.5
    }

    return Policy(
        deployment_cap  = float(dims["deployment_cap"]),
        transparency    = float(dims["transparency"]),
        enforcement     = float(dims["enforcement"]),
        audit_intensity = float(dims["audit_intensity"]),
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
        Per-dimension ideology sensitivity. When None, falls back to the
        legacy hardcoded AI-policy bias for 4-dim vectors, or zeros otherwise.
    noise_scale : float or np.ndarray, shape (d,)
        Standard deviation of perceptual noise. Passing an array allows
        per-dimension noise (used to scale by inverse confidence in Tier 1/2).
        Default 0.05 (scalar, applied to all dimensions equally).
    rng : np.random.Generator, optional

    Returns
    -------
    np.ndarray, shape (d,)
        Agent's perceived policy vector, clamped to [0, 1].
    """
    d = len(policy_vector)

    if dimension_salience is None:
        if d == 4:
            dimension_salience = np.array([-0.3, 0.1, 0.2, 0.15])
        else:
            dimension_salience = np.zeros(d)

    bias = ideology * np.asarray(dimension_salience)

    if rng is not None:
        noise = rng.normal(0.0, noise_scale, size=d)
    else:
        noise = np.random.normal(0.0, noise_scale, size=d)

    perceived = trust * (policy_vector + bias) + noise
    return np.clip(perceived, 0.0, 1.0)


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
