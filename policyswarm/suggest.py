"""
policyswarm.suggest
===================
Propose an opinion space from text: dimensions from a topic model, then
keyword rules from a System One decision model.

An ``OpinionSpace`` (see ``opinion_space.py``) needs dimensions and, to derive
a policy position from text, keyword rules of the form "this phrase moves that
dimension by so much". Both used to be written by hand. This module drafts
them in two independent stages:

Stage 1, topics -> dimensions (needs scikit-learn: ``pip install -e ".[topics]"``)
    ``find_topics`` runs NMF on TF-IDF over sentences. Each topic is a
    weighted list of terms. A topic model cannot name a topic, so the name is
    a placeholder (the top term) for a person to replace.

Stage 2, phrases -> keyword rules (needs laya: ``pip install -e ".[decision]"``)
    ``rate_keywords`` asks a decision model fixed questions about each
    candidate phrase: which dimension it bears on (or none), whether it
    raises or lowers that dimension, and how strongly. The answers map
    directly onto a ``KeywordRule``.

Everything returned is a *suggestion*. Nothing here runs inside a simulation:
the output is an opinion-space description that a person reviews, and the
deterministic keyword path then turns it into a ``Policy``.

A decision model returns one of the offered options every time, so a wrong
answer looks exactly like a right one, and its stated probability is not a
reliable guide. ``policyswarm/tools/eval_suggest.py`` measures agreement with
the built-in keyword table.
"""

from __future__ import annotations

import importlib.util
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

from .experiments.params import ParamError
from .extraction_embedding import _chunk_text, _read_pdf
from .opinion_space import MAX_DIMENSIONS, MIN_DIMENSIONS, Dimension, KeywordRule, OpinionSpace

#: Terms kept per topic, and candidate phrases taken from each topic for stage 2.
TERMS_PER_TOPIC = 10
PHRASES_PER_TOPIC = 8
#: Most phrases one request will rate (each is a model call).
MAX_PHRASES = 40
#: Corpus folder limits.
MAX_CORPUS_FILES = 200
MAX_CORPUS_BYTES = 20 * 1024 * 1024
_CORPUS_SUFFIXES = {".txt", ".md", ".pdf"}

#: Answer below this probability is flagged for a closer look. On the benchmark
#: (2026-10-12) rules at or above 0.5 were right somewhat more often (dev 0.62
#: against 0.56 overall, held-out 0.77 against 0.66), on about 20 rules each:
#: a weak guide, not a guarantee.
LOW_CONFIDENCE = 0.5

#: A topic term is a candidate only if at least this share of its weight sits in one topic.
MIN_EXCLUSIVITY = 0.6
#: ... and it occurs in at most this share of the policy text's sentences. A word
#: found everywhere in a document ("ai" in an AI policy) says nothing about one dimension.
MAX_SENTENCE_SHARE = 0.25
#: Policy filler that survives the English stop-word list.
BOILERPLATE = frozenset("""
    shall hereby thereof herein pursuant including include includes based use used using
    apply applies applicable provide provides provided ensure ensures set sets
    act article section chapter schedule annex paragraph clause provisions provision
    policy policies framework system systems measures measure practices practice
    entity entities body bodies authority authorities government state states member
    general specific relevant appropriate annual year years new existing
""".split())

#: Ways of asking the decision model which dimension a phrase bears on.
#:
#: Measured with ``tools/eval_suggest.py`` on the dev domains (104 phrases,
#: Laya zero-shot, 2026-10-12), as precision / recall / share of "none"
#: phrases wrongly given a rule:
#:
#:   many_way, descriptions only      0.56 / 0.38 / 0.25   <- the default
#:   many_way, with the two ends      0.32 / 0.38 / 0.96
#:   yes_no, with the two ends        0.27 / 0.35 / 1.00
#:   three_way, with the two ends     0.25 / 0.33 / 1.00
#:   word-overlap baseline (no model) 0.41 / 0.38 / 0.12
#:
#: The per-dimension questions and the longer descriptions made the model stop
#: answering "none", so every phrase got a rule. The alternatives are kept for
#: re-testing with a fine-tuned or different model.
STRATEGIES = ("many_way", "yes_no", "three_way")
DEFAULT_STRATEGY = "many_way"
#: Keyword delta for each strength answer, on the -1..1 scale. The built-in
#: table's rules span 0.2 to 0.7.
STRENGTH_DELTAS = {"weak": 0.2, "moderate": 0.4, "strong": 0.6}
NO_DIMENSION = "none of these"


def available() -> Dict[str, bool]:
    """Which stages can run in this environment."""
    return {
        "topics"  : importlib.util.find_spec("sklearn") is not None,
        "keywords": importlib.util.find_spec("laya") is not None,
    }


# ---------------------------------------------------------------------------
# Stage 1: topics
# ---------------------------------------------------------------------------

@dataclass
class Topic:
    """One topic: a weighted list of terms, and sentences that show it."""
    name     : str                    # placeholder identifier, meant to be renamed
    terms    : List[Dict[str, Any]]   # [{"term", "weight", "exclusivity"}], strongest first;
                                      # exclusivity = share of the term's weight in this topic
    examples : List[str]              # the sentences that load most on this topic

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def split_sentences(text: str) -> List[str]:
    """Sentences and list items of a document, with very short fragments dropped."""
    pieces = re.split(r"(?<=[.!?;:])\s+|\n+", text)
    return [p.strip(" \t*-") for p in pieces if len(p.split()) >= 4]


def load_texts(policy_text: str, corpus_dir: Optional[str] = None) -> List[str]:
    """The text units a topic model is fitted on.

    The policy text is split into sentences. With ``corpus_dir``, every
    ``.txt`` / ``.md`` / ``.pdf`` file in that folder is added as chunks of
    about 60 words, so a long document does not count as one unit.
    """
    texts = split_sentences(policy_text)
    if corpus_dir:
        folder = Path(corpus_dir).expanduser()
        if not folder.is_dir():
            raise ParamError(f"corpus folder not found: {corpus_dir}")
        files = sorted(f for f in folder.iterdir() if f.suffix.lower() in _CORPUS_SUFFIXES)
        if not files:
            raise ParamError(f"no .txt, .md or .pdf files in {corpus_dir}")
        if len(files) > MAX_CORPUS_FILES:
            raise ParamError(f"corpus folder has {len(files)} files; the limit is {MAX_CORPUS_FILES}")
        if sum(f.stat().st_size for f in files) > MAX_CORPUS_BYTES:
            raise ParamError("corpus folder is larger than 20 MB")
        for file in files:
            body = _read_pdf(file) if file.suffix.lower() == ".pdf" \
                else file.read_text(encoding="utf-8", errors="replace")
            texts.extend(chunk for chunk in _chunk_text(body, max_words=60, stride=0) if chunk.strip())
    return texts


def _identifier(term: str, taken: set) -> str:
    """A valid, unused dimension name made from a term."""
    base = re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")[:36] or "topic"
    if not base[0].isalpha():
        base = "t_" + base
    name, n = base, 2
    while name in taken:
        name, n = f"{base}_{n}", n + 1
    taken.add(name)
    return name


def find_topics(texts: Sequence[str], n_topics: int = 4, seed: int = 0) -> List[Topic]:
    """Fit NMF on TF-IDF and return ``n_topics`` topics, most prominent first.

    Deterministic for a given ``seed``. Terms are single words and two-word
    phrases, with English stop words removed.
    """
    if not MIN_DIMENSIONS <= n_topics <= MAX_DIMENSIONS:
        raise ParamError(f"n_topics: choose {MIN_DIMENSIONS} to {MAX_DIMENSIONS}")
    if len(texts) < 2 * n_topics:
        raise ParamError(
            f"Too little text for {n_topics} topics: found {len(texts)} sentences and need "
            f"at least {2 * n_topics}. Use fewer topics, a longer text or a corpus folder.")
    try:
        from sklearn.decomposition import NMF
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        raise ParamError('Topic modelling needs scikit-learn: pip install -e ".[topics]"') from None

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1,
                                 sublinear_tf=True, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]+\b")
    matrix = vectorizer.fit_transform(texts)
    vocabulary = vectorizer.get_feature_names_out()
    if len(vocabulary) < n_topics:
        raise ParamError("Too few distinct words to form topics.")
    model = NMF(n_components=n_topics, init="nndsvda", random_state=seed, max_iter=500)
    loadings = model.fit_transform(matrix)             # (texts, topics)

    order = loadings.sum(axis=0).argsort()[::-1]       # most prominent topic first
    taken: set = set()
    topics = []
    for k in order:
        weights = model.components_[k]
        top = [i for i in weights.argsort()[::-1][:TERMS_PER_TOPIC] if weights[i] > 0]
        if not top:
            continue
        best = loadings[:, k].argsort()[::-1][:2]
        share = weights / np.maximum(model.components_.sum(axis=0), 1e-12)
        topics.append(Topic(
            name     = _identifier(vocabulary[top[0]], taken),
            terms    = [{"term": str(vocabulary[i]), "weight": round(float(weights[i]), 4),
                         "exclusivity": round(float(share[i]), 3)} for i in top],
            examples = [texts[i] for i in best if loadings[i, k] > 0],
        ))
    return topics


def occurs_in(phrase: str, text: str) -> bool:
    """Whether a keyword rule for ``phrase`` would fire on ``text`` (same test as the extractor)."""
    return re.search(r"\b" + re.escape(phrase.lower()) + r"\b", text.lower()) is not None


def is_generic(term: str) -> bool:
    """Whether every word of a term is policy boilerplate."""
    return all(word in BOILERPLATE for word in term.lower().split())


def candidate_phrases(topics: Sequence[Topic], policy_text: str,
                      per_topic: int = PHRASES_PER_TOPIC, selective: bool = True) -> List[str]:
    """Topic terms worth rating, without repeats.

    Always: the term must occur in the policy text, because keyword rules are
    only ever matched against that text. With ``selective`` (the default) a
    term is also dropped when it

      * is policy boilerplate (``BOILERPLATE``);
      * is spread across topics (``MIN_EXCLUSIVITY``), so it cannot stand for one;
      * occurs in more of the text's sentences than a single topic should
        (``MAX_SENTENCE_SHARE``, or 1.5 / number of topics if that is larger);
      * is a single word contained in a longer kept phrase ("annual" when
        "annual turnover" is kept).
    """
    sentences = split_sentences(policy_text) if selective else []
    # A term that marks one of n topics should sit in roughly 1/n of the sentences.
    limit = max(MAX_SENTENCE_SHARE, 1.5 / max(len(topics), 1))
    kept: List[str] = []
    for topic in topics:
        chosen = []
        for entry in topic.terms:
            term = entry["term"]
            if term in kept or term in chosen or not occurs_in(term, policy_text):
                continue
            if selective:
                if is_generic(term) or entry.get("exclusivity", 1.0) < MIN_EXCLUSIVITY:
                    continue
                if sum(occurs_in(term, x) for x in sentences) > limit * len(sentences):
                    continue
            chosen.append(term)
        kept.extend(chosen[:per_topic])
    if selective:
        longer = [phrase for phrase in kept if " " in phrase]
        kept = [phrase for phrase in kept
                if " " in phrase or not any(occurs_in(phrase, other) for other in longer)]
    return kept[:MAX_PHRASES]


def sentence_with(phrase: str, text: str) -> str:
    """The first sentence of ``text`` that contains ``phrase`` (context for the model)."""
    for sentence in split_sentences(text):
        if occurs_in(phrase, sentence):
            return sentence[:400]
    return ""


# ---------------------------------------------------------------------------
# Stage 2: keyword rules from a decision model
# ---------------------------------------------------------------------------

class Decider(Protocol):
    """A System One model: fixed questions in, one option per question out."""

    def decide(self, states: List[dict], questions: Dict[str, dict]) -> List[Dict[str, dict]]:
        """For each state, ``{question id: {"choice": str, "probabilities": {option: p}}}``."""


DEFAULT_CHECKPOINT = "convaiinnovations/laya"


class LayaDecider:
    """Laya, loaded once per checkpoint and process.

    ``checkpoint`` is a model id (the stock ``convaiinnovations/laya``) or the
    folder of a fine-tuned checkpoint written by ``laya-train``. Runs offline
    against the cached model when one is present.
    """

    _lock = threading.Lock()
    _agents: Dict[str, Any] = {}

    def __init__(self, checkpoint: str = DEFAULT_CHECKPOINT):
        self.checkpoint = str(checkpoint)

    @staticmethod
    def _load_agent(checkpoint: str):
        import os
        import warnings
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        try:
            import laya
        except ImportError:
            raise ParamError('Keyword suggestion needs laya: pip install -e ".[decision]"') from None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # "confidences are uncalibrated"
            return laya.load(checkpoint)

    def _load(self):
        with LayaDecider._lock:
            if self.checkpoint not in LayaDecider._agents:
                LayaDecider._agents[self.checkpoint] = self._load_agent(self.checkpoint)
            return LayaDecider._agents[self.checkpoint]

    def decide(self, states: List[dict], questions: Dict[str, dict]) -> List[Dict[str, dict]]:
        agent = self._load()
        with LayaDecider._lock:
            return [result["answers"] for result in agent.predict_batch(states, questions)]


@dataclass
class SuggestedRule:
    """A keyword rule proposed by the decision model, with how sure it claimed to be."""
    keyword        : str
    dimension      : str
    delta          : float
    confidence     : float      # the lowest of the three answers' probabilities
    low_confidence : bool

    def to_rule(self) -> KeywordRule:
        return KeywordRule(self.keyword, self.dimension, self.delta)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _meaning(dimension: Dimension, use_ends: bool = True) -> str:
    """What the model is told a dimension is about."""
    text = dimension.description or dimension.name.replace("_", " ")
    if use_ends and dimension.positive_means and dimension.negative_means:
        text += f" Positive end: {dimension.positive_means}. Negative end: {dimension.negative_means}."
    return text


def _has_ends(dimension: Dimension, use_ends: bool) -> bool:
    return bool(use_ends and dimension.positive_means and dimension.negative_means)


def _with_dimension(state: dict, dimension: Dimension, use_ends: bool) -> dict:
    return {**state, "aspect_name": dimension.name.replace("_", " "),
            "aspect_meaning": _meaning(dimension, use_ends)}


def _probability(answer: dict, option: str) -> float:
    return float(answer["probabilities"].get(option, 0.0))


#: (dimension name or None, direction or None, probability of that answer)
Assignment = Tuple[Optional[str], Optional[str], float]


def many_way_question(dimensions: Sequence[Dimension], use_ends: bool = False) -> Dict[str, dict]:
    """The "which dimension, or none?" question, as asked by the default strategy."""
    criteria = {d.name: _meaning(d, use_ends) for d in dimensions}
    criteria[NO_DIMENSION] = "The phrase is generic and says nothing specific about any of the above."
    return {"aspect": {
        "type": "choice",
        "instructions": "Which aspect of the policy does this phrase bear on most directly?",
        "criteria": criteria,
    }}


def _assign_many_way(decider, states, dimensions, use_ends) -> List[Assignment]:
    """One question per phrase: which of all the dimensions, or none?"""
    out = []
    for answers in decider.decide(list(states), many_way_question(dimensions, use_ends)):
        choice = answers["aspect"]["choice"]
        out.append((choice if choice != NO_DIMENSION else None, None,
                    _probability(answers["aspect"], choice)))
    return out


def _per_dimension(decider, states, dimensions, use_ends, question) -> List[List[dict]]:
    """Ask ``question`` about every (phrase, dimension) pair; answers[phrase][dimension]."""
    pairs = [_with_dimension(state, d, use_ends) for state in states for d in dimensions]
    flat = decider.decide(pairs, question)
    n = len(dimensions)
    return [flat[i * n:(i + 1) * n] for i in range(len(states))]


def _assign_yes_no(decider, states, dimensions, use_ends) -> List[Assignment]:
    """One yes/no question per (phrase, dimension); the strongest "yes" wins."""
    question = {"bears_on": {
        "type": "choice",
        "instructions": "Does this phrase say something specific about this aspect of the policy?",
        "criteria": {"yes": "The phrase is clearly about this aspect.",
                     "no": "The phrase is generic, or about something else."},
    }}
    out = []
    for answers in _per_dimension(decider, states, dimensions, use_ends, question):
        yes = [_probability(a["bears_on"], "yes") for a in answers]
        best = int(np.argmax(yes))
        out.append((dimensions[best].name, None, yes[best]) if yes[best] > 0.5
                   else (None, None, 1.0 - yes[best]))
    return out


def _assign_three_way(decider, states, dimensions, use_ends) -> List[Assignment]:
    """One question per (phrase, dimension) that settles dimension and direction together."""
    out = []
    grid = []
    for d in dimensions:           # the options differ per dimension, so one call each
        positive = d.positive_means if _has_ends(d, use_ends) else "the positive end described"
        negative = d.negative_means if _has_ends(d, use_ends) else "the negative end described"
        question = {"effect": {
            "type": "choice",
            "instructions": "What does this phrase signal about this aspect of the policy?",
            "criteria": {"toward_positive": f"It points toward: {positive}.",
                         "toward_negative": f"It points toward: {negative}.",
                         "unrelated": "The phrase is generic, or about something else."},
        }}
        grid.append(decider.decide([_with_dimension(s, d, use_ends) for s in states], question))
    for i in range(len(states)):
        related = [1.0 - _probability(grid[k][i]["effect"], "unrelated") for k in range(len(dimensions))]
        best = int(np.argmax(related))
        answer = grid[best][i]["effect"]
        if answer["choice"] == "unrelated":
            out.append((None, None, _probability(answer, "unrelated")))
            continue
        up, down = _probability(answer, "toward_positive"), _probability(answer, "toward_negative")
        out.append((dimensions[best].name, "raises" if up >= down else "lowers", max(up, down)))
    return out


_ASSIGN = {"many_way": _assign_many_way, "yes_no": _assign_yes_no, "three_way": _assign_three_way}

_STRENGTH_QUESTION = {
    "type": "choice",
    "instructions": "How strongly does this phrase signal that?",
    "criteria": {"weak": "A mild or incidental signal.",
                 "moderate": "A clear signal.",
                 "strong": "A decisive, emphatic signal."},
}


def direction_question(dimension: Dimension, use_ends: bool = False) -> dict:
    if _has_ends(dimension, use_ends):
        criteria = {"raises": f"It points toward: {dimension.positive_means}.",
                    "lowers": f"It points toward: {dimension.negative_means}."}
    else:
        criteria = {"raises": "It pushes the position toward the positive end described.",
                    "lowers": "It pushes the position toward the negative end described."}
    return {
        "type": "choice",
        "instructions": "When a policy document uses this phrase, which way does it move the "
                        "policy's position on this aspect?",
        "criteria": criteria,
    }


def rate_keywords(
    decider     : Decider,
    phrases     : Sequence[str],
    dimensions  : Sequence[Dimension],
    context     : str  = "",
    strategy    : str  = DEFAULT_STRATEGY,
    use_ends    : bool = False,
    use_context : bool = True,
) -> List[SuggestedRule]:
    """Turn candidate phrases into suggested keyword rules.

    First the model assigns each phrase to a dimension or to none, by one of
    three strategies:

      ``many_way``   one question per phrase with every dimension as an option;
      ``yes_no``     one yes/no question per (phrase, dimension);
      ``three_way``  per (phrase, dimension): toward the positive end, toward
                     the negative end, or unrelated (also settles direction).

    Then, for assigned phrases, it is asked the direction (unless already
    settled) and the strength. State fields are named so that none equals an
    answer option, which otherwise biases the model toward that option.

    Parameters
    ----------
    phrases : sequence of str
        At most ``MAX_PHRASES``.
    dimensions : sequence of Dimension
        Their descriptions are what the model reads; with ``use_ends`` also
        ``positive_means`` / ``negative_means``. Off by default: showing the
        ends made results worse (see ``STRATEGIES``).
    context : str
        The policy text. With ``use_context`` the sentence containing each
        phrase is shown to the model.
    """
    if strategy not in _ASSIGN:
        raise ParamError(f"strategy: {strategy!r} is not one of {list(STRATEGIES)}")
    if len(phrases) > MAX_PHRASES:
        raise ParamError(f"At most {MAX_PHRASES} phrases can be rated at once (got {len(phrases)})")
    if not phrases:
        return []
    dimensions = list(dimensions)
    by_name = {d.name: d for d in dimensions}
    states = [{"phrase": p, "used_in": sentence_with(p, context)} if use_context else {"phrase": p}
              for p in phrases]

    assigned = [(state, *assignment)
                for state, assignment in zip(states, _ASSIGN[strategy](decider, states, dimensions, use_ends))
                if assignment[0] is not None]
    if not assigned:
        return []

    # Direction and strength, one call per dimension because the options name its two ends.
    details: Dict[int, Tuple[str, float, str, float]] = {}
    for dimension in dimensions:
        rows = [i for i, (_, name, _, _) in enumerate(assigned) if name == dimension.name]
        if not rows:
            continue
        questions = {"strength": _STRENGTH_QUESTION}
        if strategy != "three_way":
            questions["direction"] = direction_question(dimension, use_ends)
        answers = decider.decide([_with_dimension(assigned[i][0], dimension, use_ends) for i in rows],
                                 questions)
        for i, answer in zip(rows, answers):
            _, _, direction, p = assigned[i]
            if "direction" in answer:
                direction = answer["direction"]["choice"]
                p_direction = _probability(answer["direction"], direction)
            else:
                p_direction = p
            strength = answer["strength"]["choice"]
            details[i] = (direction, p_direction, strength, _probability(answer["strength"], strength))

    rules = []
    for i, (state, name, _, p_dimension) in enumerate(assigned):
        direction, p_direction, strength, p_strength = details[i]
        confidence = min(p_dimension, p_direction, p_strength)
        rules.append(SuggestedRule(
            keyword        = state["phrase"].lower(),
            dimension      = by_name[name].name,
            delta          = (1.0 if direction == "raises" else -1.0) * STRENGTH_DELTAS[strength],
            confidence     = round(confidence, 3),
            low_confidence = confidence < LOW_CONFIDENCE,
        ))
    return rules


# ---------------------------------------------------------------------------
# Both stages
# ---------------------------------------------------------------------------

def propose_opinion_space(
    policy_text : str,
    n_topics    : int               = 4,
    corpus_dir  : Optional[str]     = None,
    decider     : Optional[Decider] = None,
    seed        : int               = 0,
) -> Dict[str, Any]:
    """Draft an opinion space from text: topics as dimensions, then keyword rules.

    Returns ``{"opinion_space": dict, "topics": [...], "rules": [...]}``. The
    dimension names are placeholders taken from each topic's top term, and the
    descriptions are the topic's terms, so the decision model has little to go
    on until a person rewrites them; reviewing the result is part of the method.
    """
    topics = find_topics(load_texts(policy_text, corpus_dir), n_topics, seed)
    dimensions = [Dimension(t.name, "About: " + ", ".join(x["term"] for x in t.terms[:6]) + ".")
                  for t in topics]
    rules = rate_keywords(decider or LayaDecider(), candidate_phrases(topics, policy_text),
                          dimensions, policy_text)
    space = OpinionSpace(
        dimensions         = dimensions,
        violator_dimension = dimensions[0].name,
        violator_threshold = 0.6,
        keywords           = [r.to_rule() for r in rules],
    )
    space.validate()
    return {"opinion_space": space.to_dict(), "topics": [t.to_dict() for t in topics],
            "rules": [r.to_dict() for r in rules]}
