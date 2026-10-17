"""
Check that a response letter claims only what the manuscript contains.

Every manuscript anchor in the letter is written in backticks as a LaTeX label
(`sec:...`, `tab:...`, `fig:...`, `app:...`, `lem:...`, `prop:...`) or a
citation key (`cite:key`). The script checks that:

- each label is defined in main.tex;
- each citation key is cited in main.tex and present in refs.bib;
- every key in refs.bib is cited in main.tex (otherwise it will not print);
- every number macro the letter names (`\\Vname`) is defined in numbers.tex.

    python review/check_response.py review/round3/RESPONSE.md
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def main(letter_path: str) -> int:
    letter = Path(letter_path).read_text(encoding="utf-8")
    tex = (HERE / "main.tex").read_text(encoding="utf-8")
    bib = (HERE / "refs.bib").read_text(encoding="utf-8")
    numbers = (HERE / "numbers.tex").read_text(encoding="utf-8")

    labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
    cited = {k.strip() for g in re.findall(r"\\cite[pt]?\{([^}]+)\}", tex) for k in g.split(",")}
    cited |= {k.strip() for g in re.findall(r"\\citealp\{([^}]+)\}", tex) for k in g.split(",")}
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    macros = set(re.findall(r"\\newcommand\{\\(\w+)\}", numbers))

    problems = []
    for anchor in re.findall(r"`((?:sec|tab|fig|app|lem|prop):[\w.-]+)`", letter):
        if anchor not in labels:
            problems.append(f"label not in main.tex: {anchor}")
    for key in re.findall(r"`cite:([\w.-]+)`", letter):
        if key not in cited:
            problems.append(f"citation not cited in main.tex: {key}")
        if key not in keys:
            problems.append(f"citation not in refs.bib: {key}")
    for key in sorted(keys - cited):
        problems.append(f"refs.bib entry never cited (will not print): {key}")
    for name in re.findall(r"`\\(V\w+)`", letter):
        if name not in macros:
            problems.append(f"number macro not defined: {name}")

    n_anchors = len(re.findall(r"`(?:sec|tab|fig|app|lem|prop|cite):[\w.-]+`", letter))
    print(f"{n_anchors} anchors checked; {len(problems)} problems")
    for p in problems:
        print("  -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
