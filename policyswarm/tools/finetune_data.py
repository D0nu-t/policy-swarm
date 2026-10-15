"""
policyswarm.tools.finetune_data
===============================
Prepare training data for fine-tuning the keyword-suggestion model (Laya).

**Status: head-only fine-tuning was tried on 2026-10-12 and did not help.**
Full (encoder) fine-tuning has not been run. This script converts labelled
phrases into the file ``laya-train`` reads.

What was tried
--------------
Training data: ``tests/data/keyword_training.json``, 603 phrases over ten
policy domains (1,057 rows), none shared with the benchmark. Encoder frozen
(``--freeze-encoder``), CPU, ``--shuffle-options``, ``--grad-accum 1``. Scores
on the benchmark's dev domains (104 phrases), as precision / recall / share of
"none" phrases given a rule:

    zero-shot                                   0.56 / 0.38 / 0.25
    default objective (rlcd), lr 1e-4, 3 epochs 0.54 / 0.38 / 0.29
    default objective (rlcd), lr 1e-3, 3 epochs 0.56 / 0.38 / 0.25
    soft-ce, lr 3e-4, 6 epochs                  0.41 / 0.46 / 0.58
    soft-ce, lr 3e-4, 12 epochs                 0.35 / 0.39 / 0.58

- With the default ``rlcd`` objective the head's weights moved (by up to 38%)
  but 102 to 104 of 104 decisions stayed the same as zero-shot, and the
  training loss never fell. Use ``--loss soft-ce`` on a dataset this small.
- With ``soft-ce`` the head learned: it picked the right dimension more often
  (48 of 80 against 37) but almost stopped answering "none", so it suggested
  many more wrong rules. Six more epochs made it worse on the dev domains
  while the training loss kept falling, i.e. it was fitting the training
  domains without generalising to new ones.
- No checkpoint beat zero-shot on precision, so none was scored on the
  held-out test domains and the dashboard default is unchanged.
- One epoch over 1,057 rows took about 11 minutes on CPU; a checkpoint is 1.6 GB.

The labels of both files were drafted by an AI assistant; see the README.

What it writes
--------------
One JSON line per labelled phrase, holding exactly what
``suggest.rate_keywords`` shows the model at prediction time (the default
``many_way`` strategy), so training and use match:

    {"state": {"phrase": ..., "used_in": ...},
     "questions": {"aspect": {...}},            # which dimension, or none
     "expected":  {"aspect": "enforcement"}}

and, for phrases that have a dimension, a second line asking the direction.

Input is a file in the format of ``tests/data/keyword_benchmark.json``.

Do not train on the benchmark
-----------------------------
``keyword_benchmark.json`` is the test. Training on any of it, including the
dev domains, makes later scores meaningless. Label *new* domains for training
(several hundred phrases; other policy areas than the four in the benchmark)
and pass that file here. The script refuses the benchmark file itself unless
``--allow-benchmark`` is given, which exists only for checking the format.

Recipe
------
    # 1. convert your own labelled file
    python -m policyswarm.tools.finetune_data my_training_domains.json --out train.jsonl

    # 2. check that laya-train accepts it (loads no weights, trains nothing)
    laya-train --data train.jsonl --dry-run

    # 3a. head only, on CPU, no new install (tried: did not beat zero-shot, see above)
    laya-train --data train.jsonl --freeze-encoder --shuffle-options --grad-accum 1 \
               --loss soft-ce --head-lr 3e-4 --epochs 6 --out ./laya-policy

    # 3b. full fine-tune: needs a CUDA build of PyTorch; the 421M-parameter
    #     encoder may not fit a 4 GB GPU even at batch size 1
    laya-train --data train.jsonl --shuffle-options --micro-batch 2 --loss soft-ce --out ./laya-policy

    # 4. score the result on the held-out domains, once
    python -m policyswarm.tools.eval_suggest --split dev --strategy many_way --no-ends --checkpoint ./laya-policy
    # ... and only if it beats zero-shot there, once:
    python -m policyswarm.tools.eval_suggest --split test --strategy many_way --no-ends --checkpoint ./laya-policy

Flag names in step 3 are those of ``laya-train`` 0.3.29; check
``laya-train --help`` for the installed version. The vendor reports large gains
from fine-tuning (0.36 to 0.77 typed-decision accuracy); that figure is
self-reported and has not been checked here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterator

from ..opinion_space import Dimension
from ..suggest import NO_DIMENSION, _with_dimension, direction_question, many_way_question
from .eval_suggest import BENCHMARK


def training_rows(domains: Dict[str, dict]) -> Iterator[Dict[str, Any]]:
    """``laya-train`` rows for every labelled item of every domain."""
    for domain in domains.values():
        dimensions = [Dimension(**d) for d in domain["dimensions"]]
        by_name = {d.name: d for d in dimensions}
        aspect = many_way_question(dimensions)
        for item in domain["items"]:
            state = {"phrase": item["phrase"], "used_in": item["sentence"]}
            yield {"state": state, "questions": aspect,
                   "expected": {"aspect": item["dimension"] or NO_DIMENSION}}
            if item["dimension"]:
                dimension = by_name[item["dimension"]]
                yield {"state": _with_dimension(state, dimension, use_ends=False),
                       "questions": {"direction": direction_question(dimension)},
                       "expected": {"direction": item["direction"]}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("labelled", help="Labelled phrases, in the benchmark's JSON format.")
    parser.add_argument("--out", required=True, help="Where to write the laya-train JSONL file.")
    parser.add_argument("--allow-benchmark", action="store_true",
                        help="Convert the benchmark itself (format check only; never train on it).")
    args = parser.parse_args()

    source = Path(args.labelled).resolve()
    if source == BENCHMARK.resolve() and not args.allow_benchmark:
        parser.error("That file is the benchmark. Training on it would make every later score "
                     "meaningless; label other domains for training.")
    domains = json.loads(source.read_text(encoding="utf-8"))["domains"]
    rows = list(training_rows(domains))
    with open(args.out, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows from {len(domains)} domain(s) to {args.out}")


if __name__ == "__main__":
    main()
