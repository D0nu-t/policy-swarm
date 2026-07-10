/**
 * index.tsx
 * ---------
 * Entry point. Parses CLI args, starts the Python subprocess via runner.ts,
 * wires events into the reducer, and renders the Ink UI.
 *
 * Usage (from the tui/ directory):
 *
 *   # Default: run all experiments, S=30, output=policyswarm_output
 *   node dist/index.js
 *
 *   # Custom seeds and output dir (forwarded verbatim to run_all.py)
 *   node dist/index.js --seeds 0 1 2 3 4 --output results_s5
 *
 *   # Specific experiments
 *   node dist/index.js --experiments lag counterfactual
 *
 *   # Custom Python binary (e.g. in a venv)
 *   node dist/index.js --python ../venv/bin/python
 *
 *   # Dry-run: print the command that would be executed without running it
 *   node dist/index.js --dry-run
 *
 * All flags not recognised by the TUI itself are forwarded to run_all.py.
 * The TUI flags (--python, --dry-run) are stripped before forwarding.
 */
export {};
