/**
 * runner.ts
 * ---------
 * Spawns the Python process and wires its stdout/stderr into the TUI's
 * callback system. Returns a kill() function for clean shutdown.
 *
 * Two environment details matter and are handled here, not left to the
 * caller:
 *
 *   1. `-u` flag on the Python invocation and `PYTHONUNBUFFERED=1` in the
 *      environment. When Python's stdout is not a TTY (which is always the
 *      case when spawned as a child process), CPython silently switches from
 *      line-buffered to fully block-buffered output. Without one of these
 *      measures, ##EVENT## lines queue invisibly until the OS pipe buffer
 *      fills or the process exits — the TUI shows no progress for minutes,
 *      then floods with updates at the end.
 *
 *   2. SIGINT (Ctrl+C) in the Ink process must propagate to the child. If
 *      the Node process exits without killing the child, `run_all.py` keeps
 *      running in the background, holding file locks on the output CSVs and
 *      wasting CPU. The cleanup function returned here sends SIGTERM so the
 *      caller can hook it into process.on("SIGINT").
 */
import { ExperimentEvent } from "./types.js";
export interface RunnerOptions {
    /** Arguments passed directly to Python, e.g. ["../run_all.py", "--seeds", "0"] */
    pythonArgs: string[];
    /** Python executable. Default "python". */
    pythonBin?: string;
    /** Working directory for the child process. Defaults to process.cwd(). */
    cwd?: string;
    /** Called for each validated ExperimentEvent. */
    onEvent: (event: ExperimentEvent) => void;
    /** Called for each raw stdout/stderr line (for the log pane). */
    onLog: (line: string) => void;
    /** Called when the child exits with its exit code (null = signal kill). */
    onExit: (code: number | null) => void;
}
/**
 * Start the Python subprocess.
 *
 * @returns A cleanup function. Call it to SIGTERM the child (e.g. on SIGINT).
 */
export declare function startRunner(opts: RunnerOptions): () => void;
