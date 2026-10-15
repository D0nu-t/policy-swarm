"""Golden regression: every experiment must reproduce its recorded results.

``tests/golden/<name>.csv`` holds the per-seed results of each experiment for
seeds 0-2 with default parameters, recorded before the structural refactor.
Any change to these numbers is a change to the model and must be deliberate:
re-record with ``python tests/test_golden.py`` and say why in the commit.

Slow (minutes). Deselect with ``pytest -m "not slow"``.
"""

from pathlib import Path

import pandas as pd
import pytest

from policyswarm.registry import EXPERIMENTS, build_experiment

GOLDEN_DIR = Path(__file__).parent / "golden"
SEEDS = [0, 1, 2]


def _run(name: str, output_dir) -> pd.DataFrame:
    return build_experiment(name, output_dir=str(output_dir), seeds=SEEDS).run()


@pytest.mark.slow
@pytest.mark.parametrize("name", list(EXPERIMENTS))
def test_experiment_matches_golden(name, tmp_path):
    actual = _run(name, tmp_path)
    # Round-trip through CSV so dtypes match the stored file exactly.
    csv = tmp_path / "actual.csv"
    actual.to_csv(csv, index=False)
    pd.testing.assert_frame_equal(
        pd.read_csv(csv), pd.read_csv(GOLDEN_DIR / f"{name}.csv"),
        check_exact=False, rtol=1e-9, atol=1e-12,
    )


if __name__ == "__main__":      # re-record the golden files
    import tempfile
    for experiment_name in EXPERIMENTS:
        with tempfile.TemporaryDirectory() as tmp:
            _run(experiment_name, tmp).to_csv(GOLDEN_DIR / f"{experiment_name}.csv", index=False)
        print("recorded", experiment_name)
