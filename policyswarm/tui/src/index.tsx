/**
 * index.tsx
 * ---------
 * Entry point. Parses CLI args, starts the Python subprocess via runner.ts,
 * wires events into the reducer, and renders the Ink UI.
 *
 * Usage (from the tui/ directory):
 *
 *   # Default: run all experiments, S=20, output=policyswarm_output
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

import React, { useReducer, useEffect } from "react";
import { render } from "ink";
import { App } from "./App.js";
import { reducer, initialState } from "./reducer.js";
import { startRunner } from "./runner.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
// ---------------------------------------------------------------------------
// Arg parsing
// ---------------------------------------------------------------------------

interface ParsedArgs {
  pythonBin: string;
  pythonArgs: string[];
  seeds: number[];
  dryRun: boolean;
}

function parseArgs(argv: string[]): ParsedArgs {
  const args = argv.slice(2); // strip "node" and "index.js"
  let pythonBin = "python";
  let dryRun = false;
  const forwarded: string[] = [];
  const seeds: number[] = [];

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === undefined) break;

    if (arg === "--python" && i + 1 < args.length) {
      pythonBin = args[i + 1] ?? "python";
      i += 2;
      continue;
    }
    if (arg === "--dry-run") {
      dryRun = true;
      i++;
      continue;
    }
    forwarded.push(arg);
    i++;
  }

  // Extract seeds from the forwarded list for the UI header display.
  // We parse them here but don't remove them from forwarded (run_all.py
  // needs them too).
  const seedIdx = forwarded.indexOf("--seeds");
  if (seedIdx !== -1) {
    let j = seedIdx + 1;
    while (j < forwarded.length) {
      const candidate = forwarded[j];
      if (candidate === undefined || candidate.startsWith("--")) break;
      const n = parseInt(candidate, 10);
      if (!isNaN(n)) seeds.push(n);
      j++;
    }
  }

  // Default seeds: 0-29 (S=30), matching run_all.py default
  const effectiveSeeds = seeds.length > 0 ? seeds : Array.from({ length: 30 }, (_, k) => k);

  // Always point at run_all.py relative to the tui/ directory


const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const runAllPath = path.resolve(__dirname, "../../../run_all.py");  const pythonArgs = [runAllPath, ...forwarded];

  return { pythonBin, pythonArgs, seeds: effectiveSeeds, dryRun };
}

// ---------------------------------------------------------------------------
// Root component — owns the reducer and starts the runner
// ---------------------------------------------------------------------------

interface RootProps {
  pythonBin: string;
  pythonArgs: string[];
  seeds: number[];
}

function Root({ pythonBin, pythonArgs, seeds }: RootProps): React.ReactElement {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);

  useEffect(() => {
    const kill = startRunner({
      pythonBin,
      pythonArgs,
      onEvent: (event) => dispatch({ kind: "event", event }),
      onLog: (line) => dispatch({ kind: "log", line }),
      onExit: (code) => dispatch({ kind: "process_exit", code }),
    });

    // Clean up (SIGTERM the child) if the Ink component unmounts — this
    // handles the case where the user presses 'q' to exit early.
    return kill;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return <App state={state} dispatch={dispatch} seeds={seeds} />;
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

const parsed = parseArgs(process.argv);

if (parsed.dryRun) {
  console.log("Dry run. Would execute:");
  console.log(`  ${parsed.pythonBin} ${parsed.pythonArgs.join(" ")}`);
  console.log(`  Seeds: ${parsed.seeds.join(", ")}`);
  process.exit(0);
}

// Register SIGINT handler before render so Ctrl+C kills the child even if
// the Ink event loop hasn't fully started yet.
let killChild: (() => void) | null = null;

// process.on("SIGINT", () => {
//   killChild?.();
//   process.exit(130);
// });

// Ink's render() returns { waitUntilExit } — await it so the Node process
// doesn't exit immediately, leaving the child orphaned.
const { waitUntilExit } = render(
  <Root
    pythonBin={parsed.pythonBin}
    pythonArgs={parsed.pythonArgs}
    seeds={parsed.seeds}
  />
);

waitUntilExit().then(() => {
  process.exit(0);
}).catch(() => {
  process.exit(1);
});
