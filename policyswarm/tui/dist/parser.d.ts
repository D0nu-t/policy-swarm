/**
 * parser.ts
 * ---------
 * Converts the raw byte stream from the Python child process into validated
 * ExperimentEvent objects.
 *
 * The central design decision: Node's `stdout.on('data')` delivers arbitrary
 * Buffer chunks, not complete lines. A line can arrive split across two or
 * more chunks. LineParser buffers incomplete content and only yields complete
 * lines, so a JSON payload split at an unlucky byte boundary doesn't produce
 * a parse error and silently disappears.
 *
 * Only lines containing the sentinel prefix "##EVENT## " are parsed as events;
 * everything else is passed through as raw log text via the log callback in
 * runner.ts. This means executive_summary() dumps, stats_df.to_string() output,
 * and other prose from Python can never accidentally be misread as events.
 */
import { ExperimentEvent } from "./types.js";
export declare const SENTINEL = "##EVENT## ";
export declare class LineParser {
    private buffer;
    /**
     * Feed a raw chunk (from a `data` event on the child's stdout pipe).
     * Returns zero or more fully-parsed events extracted from complete lines
     * in the chunk plus any previously buffered content.
     *
     * Partial lines at the end of the chunk are held in the internal buffer
     * until the next call supplies the rest.
     */
    feed(chunk: string): ExperimentEvent[];
    /**
     * Call after the process exits to drain any content remaining in the buffer
     * that was not followed by a newline. In practice this is rare (Python's
     * print() always appends \n), but handling it prevents a dropped final event
     * in tests that feed exact strings without trailing newlines.
     */
    flush(): ExperimentEvent[];
    /**
     * Parse a single complete line. Returns a validated ExperimentEvent or null.
     *
     * Failure modes that produce null (all silently discarded):
     *   - Line does not contain the sentinel prefix
     *   - JSON.parse fails (malformed JSON)
     *   - Zod schema validation fails (unexpected shape)
     *
     * The third case is the important one: an unknown event type or a missing
     * required field is rejected here at the boundary rather than propagating
     * into the reducer where a runtime crash would be harder to diagnose.
     */
    parseLine(line: string): ExperimentEvent | null;
}
