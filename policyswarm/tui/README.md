# policy-swarm/tui

TypeScript terminal UI for [PolicySwarm](../README.md) experiment runs.

Wraps `python run_all.py` in a live progress dashboard showing per-experiment
status, seed-level progress bars, and a scrolling log pane.

## Architecture

```
tui/
  src/
    types.ts       Discriminated union ExperimentEvent + Zod schemas
    parser.ts      ##EVENT## line extraction with chunk-split handling
    reducer.ts     Pure (AppState, action) => AppState
    runner.ts      spawn() wrapper with SIGINT / SIGTERM handling
    App.tsx        Ink UI component (purely presentational)
    index.tsx      CLI arg parsing, runner startup, render()
    __tests__/
      parser.test.ts   LineParser: chunk splitting, sentinel filtering, schema rejection
      reducer.test.ts  State transitions, class-name normalisation, immutability
```

### Event protocol

The Python process emits structured events as single-line JSON on stdout,
prefixed with the sentinel `##EVENT## `. The sentinel ensures the parser
can distinguish events from prose output (stats dumps, executive summaries)
without any risk of false positives.

```
##EVENT## {"type":"start","experiment":"EnforcementLagExperiment","total":150}
##EVENT## {"type":"seed_complete","experiment":"EnforcementLagExperiment","completed":7,"total":150,"condition":{"lag":20},"seed":6}
##EVENT## {"type":"complete","experiment":"EnforcementLagExperiment","figures":1,"rows":150}
##EVENT## {"type":"error","experiment":"lag","message":"ZeroDivisionError: ..."}
```

Events are emitted by `BaseExperiment._emit()` (in `experiments/base.py`)
and module-level `_emit_event()` (in `policyswarm/__init__.py`).

### Design decisions

**Why a sentinel prefix?** `run_all.py` also prints executive summaries,
stats DataFrames, and CSV paths. A sentinel that can't appear in prose
output lets the parser grep for events without heuristics.

**Why a line buffer in parser.ts?** Node's `stdout.on('data')` delivers
arbitrary chunks, not lines. A JSON payload split across two chunks would
silently drop the event without buffering.

**Why `PYTHONUNBUFFERED=1` + `-u` flag?** When spawned as a child process
stdout is not a TTY, so CPython block-buffers stdout. Without these flags
the TUI sees nothing until the process exits.

## Setup

```bash
cd tui
npm install
npm run build
```

## Usage

```bash
# From tui/ — runs all experiments with default S=20
node dist/index.js

# Custom seeds
node dist/index.js --seeds 0 1 2 3 4 5

# Specific experiments forwarded to run_all.py
node dist/index.js --experiments lag counterfactual

# Different Python binary (venv)
node dist/index.js --python ../venv/bin/python --seeds 0 1 2

# Dry run: print command without executing
node dist/index.js --dry-run --seeds 0 1 2
```

## Development

```bash
npm run typecheck   # tsc --noEmit (strict mode, noUncheckedIndexedAccess)
npm test            # vitest run
npm run test:watch  # vitest in watch mode
```

## CI

GitHub Actions runs typecheck + tests on every push or PR that touches
`tui/` or `policyswarm/experiments/base.py`. See `.github/workflows/ci.yml`.
