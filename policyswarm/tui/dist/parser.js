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
import { ExperimentEventSchema } from "./types.js";
export const SENTINEL = "##EVENT## ";
export class LineParser {
    constructor() {
        this.buffer = "";
    }
    /**
     * Feed a raw chunk (from a `data` event on the child's stdout pipe).
     * Returns zero or more fully-parsed events extracted from complete lines
     * in the chunk plus any previously buffered content.
     *
     * Partial lines at the end of the chunk are held in the internal buffer
     * until the next call supplies the rest.
     */
    feed(chunk) {
        this.buffer += chunk;
        // Split on newline; the last element is either empty (chunk ended with \n)
        // or an incomplete line fragment that must stay in the buffer.
        const parts = this.buffer.split("\n");
        // Non-null assertion safe: split("x") always returns at least one element.
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        this.buffer = parts.pop();
        const events = [];
        for (const line of parts) {
            const event = this.parseLine(line);
            if (event !== null) {
                events.push(event);
            }
        }
        return events;
    }
    /**
     * Call after the process exits to drain any content remaining in the buffer
     * that was not followed by a newline. In practice this is rare (Python's
     * print() always appends \n), but handling it prevents a dropped final event
     * in tests that feed exact strings without trailing newlines.
     */
    flush() {
        const remaining = this.buffer;
        this.buffer = "";
        if (remaining.trim() === "")
            return [];
        const event = this.parseLine(remaining);
        return event !== null ? [event] : [];
    }
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
    parseLine(line) {
        const idx = line.indexOf(SENTINEL);
        if (idx === -1)
            return null;
        const jsonStr = line.slice(idx + SENTINEL.length).trim();
        if (jsonStr === "")
            return null;
        let raw;
        try {
            raw = JSON.parse(jsonStr);
        }
        catch {
            return null;
        }
        const result = ExperimentEventSchema.safeParse(raw);
        if (!result.success) {
            return null;
        }
        return result.data;
    }
}
