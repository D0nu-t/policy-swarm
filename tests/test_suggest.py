"""Tests for drafting an opinion space from text (topics, then a decision model).

The decision model is replaced by a scripted fake, so Laya is not needed here.
"""

from pathlib import Path

import pytest

from policyswarm.experiments.params import ParamError
from policyswarm.extraction import DEFAULT_POLICY_TEXT
from policyswarm.opinion_space import Dimension, OpinionSpace
from policyswarm.suggest import (
    DEFAULT_CHECKPOINT, MAX_PHRASES, NO_DIMENSION, STRATEGIES, STRENGTH_DELTAS, LayaDecider,
    available, candidate_phrases,
    find_topics, is_generic, load_texts, occurs_in, propose_opinion_space, rate_keywords,
    sentence_with, split_sentences,
)

pytest.importorskip("sklearn")

TWO_THEMES = (
    "The harbour pilots guide every cargo ship through the narrow channel. "
    "Each cargo ship must wait for the harbour tide before entering the channel. "
    "Pilots board the ship outside the harbour and steer it past the channel buoys. "
    "A cargo ship that ignores the harbour pilots risks grounding in the channel. "
    "The orchard keeper prunes the apple trees before the spring blossom. "
    "Apple trees need pruning so the blossom sets fruit in the orchard. "
    "Bees visit the orchard blossom and pollinate the apple trees. "
    "Late frost can kill the apple blossom across the whole orchard. "
)


class FakeDecider:
    """Answers from a table: {phrase: (dimension, direction, strength, probability)}.

    Understands every question the three strategies ask, so the same table
    drives all of them.
    """

    def __init__(self, table):
        self.table = table
        self.calls = []

    def decide(self, states, questions):
        self.calls.append((states, questions))
        answers = []
        for state in states:
            dimension, direction, strength, p = self.table.get(
                state["phrase"], (NO_DIMENSION, "raises", "weak", 0.9))
            here = state.get("aspect_name", "").replace(" ", "_") == dimension
            picks = {
                "aspect"   : dimension,
                "direction": direction,
                "strength" : strength,
                "bears_on" : "yes" if here else "no",
                "effect"   : ("toward_positive" if direction == "raises" else "toward_negative")
                             if here else "unrelated",
            }
            answers.append({qid: {"choice": picks[qid], "probabilities": {picks[qid]: p}}
                            for qid in questions})
        return answers


# ---------------------------------------------------------------------------
# Stage 1: topics
# ---------------------------------------------------------------------------

def test_topics_separate_two_themes_and_are_repeatable():
    texts = load_texts(TWO_THEMES)
    assert len(texts) == 8
    topics = find_topics(texts, n_topics=2, seed=0)
    tops = [{t["term"] for t in topic.terms[:4]} for topic in topics]
    assert any({"harbour", "channel"} & top for top in tops)
    assert any({"orchard", "apple"} & top for top in tops)
    assert not ({"harbour", "channel", "ship"} & tops[0]) or not ({"orchard", "apple"} & tops[0])
    assert [t.to_dict() for t in find_topics(texts, 2, seed=0)] == [t.to_dict() for t in topics]
    for topic in topics:
        assert topic.examples and topic.name.isidentifier() and topic.name == topic.name.lower()
    assert len({t.name for t in topics}) == 2


def test_topic_limits_are_explained():
    texts = load_texts(TWO_THEMES)
    with pytest.raises(ParamError, match="n_topics"):
        find_topics(texts, n_topics=1)
    with pytest.raises(ParamError, match="Too little text"):
        find_topics(texts, n_topics=6)


def test_corpus_folder_adds_text_and_bad_folders_are_rejected(tmp_path):
    (tmp_path / "a.txt").write_text(TWO_THEMES * 3, encoding="utf-8")
    (tmp_path / "ignored.csv").write_text("x,y", encoding="utf-8")
    assert len(load_texts(TWO_THEMES, str(tmp_path))) > len(load_texts(TWO_THEMES))
    with pytest.raises(ParamError, match="not found"):
        load_texts(TWO_THEMES, str(tmp_path / "missing"))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ParamError, match="no .txt"):
        load_texts(TWO_THEMES, str(empty))


def test_candidate_phrases_all_occur_in_the_policy_text():
    topics = find_topics(load_texts(DEFAULT_POLICY_TEXT), n_topics=4)
    phrases = candidate_phrases(topics, DEFAULT_POLICY_TEXT)
    assert phrases and len(phrases) == len(set(phrases)) <= MAX_PHRASES
    assert all(occurs_in(p, DEFAULT_POLICY_TEXT) for p in phrases)
    assert occurs_in("Risk", "a risk-based rule") and not occurs_in("risk", "brisket")
    assert "channel" in sentence_with("channel", TWO_THEMES)
    assert split_sentences("Too short. This one is long enough to keep.") == ["This one is long enough to keep."]


# ---------------------------------------------------------------------------
# Stage 2: keyword rules
# ---------------------------------------------------------------------------

DIMENSIONS = [
    Dimension("shipping", "Harbour traffic.", positive_means="strict control of ships",
              negative_means="ships move freely"),
    Dimension("farming", "Orchard practice. Positive = intensive."),
]
TABLE = {
    "harbour pilots": ("shipping", "raises", "strong", 0.9),
    "frost": ("farming", "lowers", "weak", 0.55),
    "Channel": ("shipping", "raises", "moderate", 0.7),
}
PHRASES = ["harbour pilots", "frost", "whole", "Channel"]


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_answers_become_keyword_rules(strategy):
    decider = FakeDecider(TABLE)
    rules = rate_keywords(decider, PHRASES, DIMENSIONS, TWO_THEMES, strategy=strategy)

    assert [(r.keyword, r.dimension, r.delta) for r in rules] == [
        ("harbour pilots", "shipping", STRENGTH_DELTAS["strong"]),
        ("frost", "farming", -STRENGTH_DELTAS["weak"]),
        ("channel", "shipping", STRENGTH_DELTAS["moderate"]),     # keywords are stored lower-case
    ]
    assert [r.confidence for r in rules] == [0.9, 0.55, 0.7]           # "whole" was dropped
    assert not any(r.low_confidence for r in rules)
    assert rules[0].to_rule().keyword == "harbour pilots"

    for states, questions in decider.calls:
        # The model sees each phrase in its sentence.
        assert all("phrase" in state and "used_in" in state for state in states)
        # No state field shares a name with an answer option (that biases the model).
        options = {option for q in questions.values() for option in q["criteria"]}
        assert not options & set(states[0])


def test_what_each_strategy_asks():
    many = FakeDecider(TABLE)
    rate_keywords(many, PHRASES, DIMENSIONS, TWO_THEMES, strategy="many_way", use_ends=True)
    first_states, first_questions = many.calls[0]
    assert len(first_states) == 4
    assert list(first_questions["aspect"]["criteria"]) == ["shipping", "farming", NO_DIMENSION]
    # The two ends are shown when a dimension has them, and used as the direction options.
    assert "strict control of ships" in first_questions["aspect"]["criteria"]["shipping"]
    shipping_call = next(q for s, q in many.calls[1:] if s[0]["aspect_name"] == "shipping")
    assert "strict control of ships" in shipping_call["direction"]["criteria"]["raises"]
    farming_call = next(q for s, q in many.calls[1:] if s[0]["aspect_name"] == "farming")
    assert "positive end" in farming_call["direction"]["criteria"]["raises"]

    yes_no = FakeDecider(TABLE)
    rate_keywords(yes_no, PHRASES, DIMENSIONS, TWO_THEMES, strategy="yes_no")
    states, questions = yes_no.calls[0]
    assert len(states) == 4 * 2 and list(questions["bears_on"]["criteria"]) == ["yes", "no"]

    three = FakeDecider(TABLE)
    rate_keywords(three, PHRASES, DIMENSIONS, TWO_THEMES, strategy="three_way")
    assert [len(states) for states, q in three.calls if "effect" in q] == [4, 4]
    assert all("direction" not in q for _, q in three.calls)       # already settled

    bare = FakeDecider(TABLE)
    rate_keywords(bare, PHRASES, DIMENSIONS, TWO_THEMES, use_context=False)     # ends are off by default
    states, questions = bare.calls[0]
    assert "used_in" not in states[0]
    assert "strict control" not in questions["aspect"]["criteria"]["shipping"]

    unsure = rate_keywords(FakeDecider({"frost": ("farming", "lowers", "weak", 0.3)}), ["frost"], DIMENSIONS)
    assert unsure[0].low_confidence and unsure[0].confidence == 0.3

    with pytest.raises(ParamError, match="strategy"):
        rate_keywords(FakeDecider({}), ["x"], DIMENSIONS, strategy="guess")


def test_candidate_filter_drops_generic_terms():
    text = DEFAULT_POLICY_TEXT
    topics = find_topics(load_texts(text), n_topics=4)
    loose = candidate_phrases(topics, text, selective=False)
    strict = candidate_phrases(topics, text)
    assert len(strict) < len(loose)
    assert not any(is_generic(p) for p in strict) and any(is_generic(p) for p in loose)
    # A single word is dropped when a kept longer phrase contains it.
    longer = [p for p in strict if " " in p]
    assert not any(" " not in p and any(occurs_in(p, other) for other in longer) for p in strict)
    assert is_generic("framework") and is_generic("annual systems") and not is_generic("annual turnover")


def test_rating_edge_cases():
    assert rate_keywords(FakeDecider({}), [], DIMENSIONS) == []
    assert rate_keywords(FakeDecider({}), ["nothing", "matches"], DIMENSIONS) == []
    with pytest.raises(ParamError, match="At most"):
        rate_keywords(FakeDecider({}), [f"p{i}" for i in range(MAX_PHRASES + 1)], DIMENSIONS)


def test_proposed_space_is_valid_and_builds_a_policy():
    topics = find_topics(load_texts(TWO_THEMES), 2)
    name = topics[0].name
    term = next(t["term"] for t in topics[0].terms if occurs_in(t["term"], TWO_THEMES))
    proposal = propose_opinion_space(
        TWO_THEMES, n_topics=2, decider=FakeDecider({term: (name, "raises", "strong", 0.8)}))

    space = OpinionSpace.from_dict(proposal["opinion_space"])
    assert [d.name for d in space.dimensions] == [t["name"] for t in proposal["topics"]]
    assert [(r["keyword"], r["dimension"]) for r in proposal["rules"]] == [(term, name)]
    policy = space.build_policy(TWO_THEMES)
    assert policy.dim == 2
    assert policy.vector[space.dimension_names.index(name)] == pytest.approx(STRENGTH_DELTAS["strong"])


def test_availability_reports_both_stages():
    assert available()["topics"] is True and set(available()) == {"topics", "keywords"}


# ---------------------------------------------------------------------------
# Fine-tuning data and checkpoints
# ---------------------------------------------------------------------------

def test_training_set_shares_nothing_with_the_benchmark():
    from policyswarm.tools.eval_suggest import load_benchmark
    data = Path(__file__).parent / "data"
    benchmark = load_benchmark()
    training = load_benchmark(path=data / "keyword_training.json")
    assert not set(benchmark) & set(training)
    pairs = lambda domains: {(i["phrase"].lower(), i["sentence"])       # noqa: E731
                             for d in domains.values() for i in d["items"]}
    assert not pairs(benchmark) & pairs(training)
    assert {d["split"] for d in training.values()} == {"train"}
    sizes = {len(d["dimensions"]) for d in training.values()}
    assert len(sizes) >= 3, "the number of dimensions should vary across training domains"
    for domain in list(benchmark.values()) + list(training.values()):
        names = [d["name"] for d in domain["dimensions"]]
        for item in domain["items"]:
            assert item["phrase"].lower() in item["sentence"].lower()
            assert (item["dimension"] is None) == (item["direction"] is None)
            assert item["dimension"] is None or item["dimension"] in names


def test_training_rows_match_what_the_model_is_asked_at_prediction_time():
    from policyswarm.tools.finetune_data import training_rows
    domain = {"dimensions": [d.to_dict() for d in DIMENSIONS], "items": [
        {"phrase": "harbour pilots", "sentence": "The harbour pilots guide every ship.",
         "dimension": "shipping", "direction": "raises"},
        {"phrase": "whole", "sentence": "The whole orchard.", "dimension": None, "direction": None}]}
    rows = list(training_rows({"demo": domain}))
    assert [r["expected"] for r in rows] == [{"aspect": "shipping"}, {"direction": "raises"},
                                             {"aspect": NO_DIMENSION}]
    asked = FakeDecider(TABLE)
    rate_keywords(asked, ["harbour pilots"], DIMENSIONS, "The harbour pilots guide every ship.")
    (first_states, first_questions), (second_states, second_questions) = asked.calls
    assert rows[0]["state"] == first_states[0] and rows[0]["questions"] == first_questions
    assert rows[1]["state"] == second_states[0]
    assert rows[1]["questions"]["direction"] == second_questions["direction"]


def test_decider_loads_each_checkpoint_once(monkeypatch):
    loaded = []

    class Agent:
        def __init__(self, checkpoint):
            self.checkpoint = checkpoint

        def predict_batch(self, states, questions):
            return [{"answers": {"from": self.checkpoint}} for _ in states]

    monkeypatch.setattr(LayaDecider, "_agents", {})
    monkeypatch.setattr(LayaDecider, "_load_agent",
                        staticmethod(lambda checkpoint: loaded.append(checkpoint) or Agent(checkpoint)))
    stock, tuned = LayaDecider(), LayaDecider("models/tuned")
    assert stock.decide([{}], {}) == [{"from": DEFAULT_CHECKPOINT}]
    assert tuned.decide([{}], {}) == [{"from": "models/tuned"}]
    assert LayaDecider().decide([{}, {}], {}) == [{"from": DEFAULT_CHECKPOINT}] * 2
    assert loaded == [DEFAULT_CHECKPOINT, "models/tuned"]
