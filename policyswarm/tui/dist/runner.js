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
import { spawn } from "child_process";
import { LineParser } from "./parser.js";
/**
 * Start the Python subprocess.
 *
 * @returns A cleanup function. Call it to SIGTERM the child (e.g. on SIGINT).
 */
export function startRunner(opts) {
    const { pythonArgs, pythonBin = "python", cwd, onEvent, onLog, onExit, } = opts;
    // -u: unbuffered binary stdout/stderr
    const child = spawn(pythonBin, ["-u", ...pythonArgs], {
        cwd: cwd ?? process.cwd(),
        env: {
            ...process.env,
            PYTHONUNBUFFERED: "1", // belt-and-suspenders alongside -u
        },
        stdio: ["ignore", "pipe", "pipe"],
    });
    const parser = new LineParser();
    function handleChunk(chunk) {
        const text = chunk.toString("utf8");
        // Feed raw text to the log callback line by line so the log pane gets
        // clean single-line entries rather than arbitrary chunk blobs.
        for (const rawLine of text.split("\n")) {
            const trimmed = rawLine.trimEnd();
            if (trimmed.length > 0) {
                onLog(trimmed);
            }
        }
        // Feed the same text to the line parser for event extraction.
        const events = parser.feed(text);
        for (const event of events) {
            onEvent(event);
        }
    }
    child.stdout?.on("data", handleChunk);
    child.stderr?.on("data", (chunk) => {
        const text = chunk.toString("utf8");
        for (const rawLine of text.split("\n")) {
            const trimmed = rawLine.trimEnd();
            if (trimmed.length > 0) {
                onLog(`[stderr] ${trimmed}`);
            }
        }
    });
    child.on("exit", (code) => {
        // Drain any buffered content that didn't end with a newline.
        const remaining = parser.flush();
        for (const event of remaining) {
            onEvent(event);
        }
        onExit(code);
    });
    child.on("error", (err) => {
        onLog(`[runner error] ${err.message}`);
        onExit(1);
    });
    return () => {
        child.kill("SIGTERM");
    };
}
