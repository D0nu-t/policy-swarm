"""
policyswarm.tools.eval_suggest
==============================
How well does the decision model propose keyword rules?

Scores ``suggest.rate_keywords`` against ``tests/data/keyword_benchmark.json``:
208 phrases over four policy domains, each labelled with the dimension it
bears on (or none) and the direction. Two domains are *dev*, used to choose
between ways of asking the model; two are *test*, held out for a final look.

    python -m policyswarm.tools.eval_suggest --split dev --strategy all
    python -m policyswarm.tools.eval_suggest --split test --strategy yes_no
    python -m policyswarm.tools.eval_suggest --split dev --candidates      # candidate filter only
    python -m policyswarm.tools.eval_suggest --make-spot-check sheet.csv   # labels hidden, to fill in
    python -m policyswarm.tools.eval_suggest --check-spot-check sheet.csv  # agreement with the labels

Measures
--------
precision   of the rules the model suggested, the share with the right
            dimension and direction. The measure that matters most: a person
            reviews what is suggested.
recall      of the phrases that should get a rule, the share that got the right one.
none->rule  of the phrases that should get no rule, the share given one.

Baselines: always answering the commonest dimension and direction, and word
overlap between the phrase's sentence and each dimension's description.

The labels were drafted by an AI assistant and spot-checked by the author, so
treat the absolute numbers with that in mind; comparisons between variants on
the same labels are the sounder use.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..opinion_space import Dimension
from ..suggest import (
    DEFAULT_CHECKPOINT, MAX_PHRASES, STRATEGIES, Decider, LayaDecider, candidate_phrases,
    find_topics, rate_keywords,
)

BENCHMARK = Path(__file__).resolve().parents[2] / "tests" / "data" / "keyword_benchmark.json"

#: (dimension or None, direction or None, confidence or None) for one item.
Prediction = Tuple[Optional[str], Optional[str], Optional[float]]
Predictor = Callable[[List[dict], List[Dimension]], List[Prediction]]


def load_benchmark(split: Optional[str] = None, path: Path = BENCHMARK) -> Dict[str, dict]:
    """Domains of the benchmark, optionally only those of one split."""
    domains = json.loads(Path(path).read_text(encoding="utf-8"))["domains"]
    return {name: d for name, d in domains.items() if split in (None, d["split"])}


def _dimensions(domain: dict) -> List[Dimension]:
    return [Dimension(**d) for d in domain["dimensions"]]


# ---------------------------------------------------------------------------
# Predictors
# ---------------------------------------------------------------------------

def model_predictor(decider: Decider, strategy: str, use_ends: bool = True,
                    use_context: bool = True) -> Predictor:
    """Predictions from ``rate_keywords``. Each phrase is shown with its own sentence."""
    def predict(items: List[dict], dimensions: List[Dimension]) -> List[Prediction]:
        found = {}
        for start in range(0, len(items), MAX_PHRASES):
            chunk = items[start:start + MAX_PHRASES]
            context = " ".join(item["sentence"] for item in chunk)
            for rule in rate_keywords(decider, [item["phrase"] for item in chunk], dimensions,
                                      context, strategy, use_ends, use_context):
                found[rule.keyword] = rule
        out = []
        for item in items:
            rule = found.get(item["phrase"].lower())
            out.append((rule.dimension, "raises" if rule.delta > 0 else "lowers", rule.confidence)
                       if rule else (None, None, None))
        return out
    return predict


def majority_predictor(items: List[dict], dimensions: List[Dimension]) -> List[Prediction]:
    """Always the commonest dimension and direction (it never abstains)."""
    labelled = [item for item in items if item["dimension"]]
    dimension = Counter(item["dimension"] for item in labelled).most_common(1)[0][0]
    direction = Counter(item["direction"] for item in labelled).most_common(1)[0][0]
    return [(dimension, direction, None)] * len(items)


_WORD = re.compile(r"[a-z]{4,}")


def overlap_predictor(items: List[dict], dimensions: List[Dimension]) -> List[Prediction]:
    """Shared words between the sentence and each description; none if there are no shared words."""
    def stems(text: str) -> set:
        return {word[:6] for word in _WORD.findall(text.lower())}

    out = []
    for item in items:
        words = stems(item["sentence"])
        scores = [len(words & stems(f"{d.name} {d.description} {d.positive_means} {d.negative_means}"))
                  for d in dimensions]
        best = max(range(len(dimensions)), key=scores.__getitem__)
        if scores[best] == 0:
            out.append((None, None, None))
            continue
        d = dimensions[best]
        up, down = len(words & stems(d.positive_means)), len(words & stems(d.negative_means))
        out.append((d.name, "raises" if up >= down else "lowers", None))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score(domains: Dict[str, dict], predictor: Predictor) -> Dict[str, Any]:
    """Run ``predictor`` over every domain and count outcomes."""
    rows = []
    started = time.time()
    for name, domain in domains.items():
        predictions = predictor(domain["items"], _dimensions(domain))
        for item, (dimension, direction, confidence) in zip(domain["items"], predictions):
            rows.append({
                "domain": name, "phrase": item["phrase"],
                "true_dimension": item["dimension"], "true_direction": item["direction"],
                "dimension": dimension, "direction": direction, "confidence": confidence,
                "correct": dimension is not None and dimension == item["dimension"]
                           and direction == item["direction"],
                "dimension_ok": dimension == item["dimension"],
            })
    suggested = [r for r in rows if r["dimension"] is not None]
    wanted = [r for r in rows if r["true_dimension"] is not None]
    unwanted = [r for r in rows if r["true_dimension"] is None]
    correct = sum(r["correct"] for r in rows)
    return {
        "items"       : len(rows),
        "suggested"   : len(suggested),
        "correct"     : correct,
        "precision"   : correct / len(suggested) if suggested else 0.0,
        "recall"      : correct / len(wanted) if wanted else 0.0,
        "none_to_rule": sum(r["dimension"] is not None for r in unwanted) / len(unwanted) if unwanted else 0.0,
        "dimension_accuracy": sum(r["dimension_ok"] for r in rows) / len(rows),
        "seconds"     : round(time.time() - started, 1),
        "rows"        : rows,
    }


def confidence_table(rows: Sequence[dict], cuts=(0.5, 0.6, 0.7, 0.8)) -> List[Dict[str, Any]]:
    """Precision among suggested rules at or above each probability cut-off."""
    suggested = [r for r in rows if r["confidence"] is not None]
    table = []
    for cut in cuts:
        kept = [r for r in suggested if r["confidence"] >= cut]
        table.append({"cut": cut, "kept": len(kept),
                      "precision": sum(r["correct"] for r in kept) / len(kept) if kept else None})
    return table


def candidate_report(domains: Dict[str, dict]) -> List[Dict[str, Any]]:
    """Does the candidate filter drop phrases labelled "none" and keep the labelled ones?

    Each domain's benchmark sentences are treated as a document; the topic
    model and candidate filter run on it, and candidates that coincide with a
    labelled phrase are counted by whether that phrase should get a rule.
    """
    report = []
    for name, domain in domains.items():
        sentences = [item["sentence"] for item in domain["items"]]
        text = " ".join(sentences)
        labels = {item["phrase"].lower(): item["dimension"] for item in domain["items"]}
        topics = find_topics(sentences, n_topics=len(domain["dimensions"]))
        row = {"domain": name}
        for label, selective in (("before", False), ("after", True)):
            candidates = candidate_phrases(topics, text, selective=selective)
            matched = [c for c in candidates if c in labels]
            row[label] = {"candidates": len(candidates), "matched": len(matched),
                          "should_have_rule": sum(labels[c] is not None for c in matched),
                          "should_not": sum(labels[c] is None for c in matched)}
        report.append(row)
    return report


# ---------------------------------------------------------------------------
# Spot check: a person labels a sample without seeing the benchmark's labels
# ---------------------------------------------------------------------------

_SHEET_COLUMNS = ["n", "domain", "phrase", "sentence", "choices", "your_dimension", "your_direction"]


def make_spot_check(path: str, per_domain: int = 10, seed: int = 0, labelled: Path = BENCHMARK) -> int:
    """Write a CSV of randomly drawn items with empty answer columns.

    ``your_dimension`` takes one of the names in ``choices`` (or ``none``);
    ``your_direction`` takes ``raises`` or ``lowers`` (blank for ``none``).
    """
    rng = random.Random(seed)
    rows = []
    for name, domain in load_benchmark(path=labelled).items():
        choices = " | ".join([d["name"] for d in domain["dimensions"]] + ["none"])
        for item in rng.sample(domain["items"], per_domain):
            rows.append({"domain": name, "phrase": item["phrase"], "sentence": item["sentence"],
                         "choices": choices, "your_dimension": "", "your_direction": ""})
    rng.shuffle(rows)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=_SHEET_COLUMNS)
        writer.writeheader()
        for n, row in enumerate(rows, 1):
            writer.writerow({"n": n, **row})
    return len(rows)


def check_spot_check(path: str, labelled: Path = BENCHMARK) -> Dict[str, Any]:
    """Compare a filled-in sheet with the labels of the file it was drawn from."""
    labels = {(name, item["phrase"]): item
              for name, domain in load_benchmark(path=labelled).items() for item in domain["items"]}
    disagreements, filled = [], 0
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            dimension = (row["your_dimension"] or "").strip().lower()
            if not dimension:
                continue
            filled += 1
            direction = (row["your_direction"] or "").strip().lower() or None
            dimension = None if dimension == "none" else dimension
            truth = labels[(row["domain"], row["phrase"])]
            if dimension != truth["dimension"] or (dimension and direction != truth["direction"]):
                disagreements.append({
                    "n": row["n"], "domain": row["domain"], "phrase": row["phrase"],
                    "yours": f"{dimension or 'none'} {direction or ''}".strip(),
                    "benchmark": f"{truth['dimension'] or 'none'} {truth['direction'] or ''}".strip()})
    return {"filled": filled, "agree": filled - len(disagreements), "disagreements": disagreements}


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _line(label: str, result: Dict[str, Any]) -> str:
    return (f"{label:<34} {result['precision']:>9.2f} {result['recall']:>7.2f} "
            f"{result['none_to_rule']:>10.2f} {result['suggested']:>9} {result['seconds']:>7.0f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--strategy", default="all",
                        help=f"One of {list(STRATEGIES)}, or 'all' (default).")
    parser.add_argument("--no-ends", action="store_true",
                        help="Hide each dimension's positive / negative end descriptions.")
    parser.add_argument("--no-context", action="store_true",
                        help="Show the model the phrase alone, without its sentence.")
    parser.add_argument("--candidates", action="store_true",
                        help="Only report the candidate filter (no decision model needed).")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT,
                        help="Laya checkpoint to score: a model id or a fine-tuned folder.")
    parser.add_argument("--out", help="Write the full results, with per-item rows, to this JSON file.")
    parser.add_argument("--make-spot-check", metavar="CSV",
                        help="Write a sample of items with the labels hidden, for a person to label.")
    parser.add_argument("--labelled", default=str(BENCHMARK),
                        help="Labelled file the spot-check commands draw from (default: the benchmark).")
    parser.add_argument("--per-domain", type=int, default=10,
                        help="Items per domain in a new spot-check sheet (default 10).")
    parser.add_argument("--check-spot-check", metavar="CSV",
                        help="Compare a filled-in spot-check sheet with the benchmark labels.")
    args = parser.parse_args()

    if args.make_spot_check:
        count = make_spot_check(args.make_spot_check, args.per_domain, labelled=Path(args.labelled))
        print(f"Wrote {count} items to {args.make_spot_check}")
        return
    if args.check_spot_check:
        result = check_spot_check(args.check_spot_check, Path(args.labelled))
        print(f"{result['agree']} of {result['filled']} filled-in items agree with the drafted labels")
        for d in result["disagreements"]:
            print(f"  #{d['n']} {d['domain']}: {d['phrase']!r}  you: {d['yours']}  benchmark: {d['benchmark']}")
        return

    domains = load_benchmark(args.split)
    if args.candidates:
        for row in candidate_report(domains):
            print(row["domain"])
            for label in ("before", "after"):
                r = row[label]
                print(f"  {label:<6} {r['candidates']:>3} candidates; of the {r['matched']} that are "
                      f"labelled: {r['should_have_rule']} should get a rule, {r['should_not']} should not")
        return

    results = {"majority baseline": score(domains, majority_predictor),
               "word-overlap baseline": score(domains, overlap_predictor)}
    strategies = STRATEGIES if args.strategy == "all" else (args.strategy,)
    decider = LayaDecider(args.checkpoint)
    for strategy in strategies:
        label = strategy + (" no-ends" if args.no_ends else "") + (" no-context" if args.no_context else "")
        results[label] = score(domains, model_predictor(decider, strategy, not args.no_ends,
                                                        not args.no_context))
        print(f"finished {label}", flush=True)

    print(f"\nsplit: {args.split} ({', '.join(domains)}; {results['majority baseline']['items']} items)")
    print(f"{'':<34} {'precision':>9} {'recall':>7} {'none->rule':>10} {'suggested':>9} {'time':>8}")
    for label, result in results.items():
        print(_line(label, result))
    for label, result in results.items():
        if "baseline" in label:
            continue
        cuts = "  ".join(f">={c['cut']}: {c['kept']} kept, "
                         + (f"{c['precision']:.2f}" if c["precision"] is not None else "n/a")
                         for c in confidence_table(result["rows"]))
        print(f"probability vs precision, {label}: {cuts}")
    if args.out:
        Path(args.out).write_text(json.dumps({"split": args.split, "results": results}, indent=1),
                                  encoding="utf-8")


if __name__ == "__main__":
    main()
