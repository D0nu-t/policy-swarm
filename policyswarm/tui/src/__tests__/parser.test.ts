/**
 * parser.test.ts
 * --------------
 * Tests for LineParser. Focus areas:
 *
 *   1. Happy path: complete event lines are parsed correctly.
 *   2. Chunk splitting: a JSON payload split across two chunks is reassembled
 *      before parsing. This is the critical real-world failure mode.
 *   3. Sentinel filtering: prose lines without ##EVENT## are ignored.
 *   4. Schema rejection: JSON that doesn't match ExperimentEventSchema is
 *      silently discarded rather than propagating a malformed object.
 *   5. flush(): content remaining in buffer after process exit is handled.
 */

import { describe, it, expect } from "vitest";
import { LineParser, SENTINEL } from "../parser.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function line(json: object): string {
  return `${SENTINEL}${JSON.stringify(json)}\n`;
}

function prose(text: string): string {
  return `${text}\n`;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LineParser", () => {
  it("parses a complete start event in a single chunk", () => {
    const parser = new LineParser();
    const events = parser.feed(
      line({ type: "start", experiment: "EnforcementLagExperiment", total: 150 })
    );
    expect(events).toHaveLength(1);
    const ev = events[0];
    expect(ev?.type).toBe("start");
    if (ev?.type === "start") {
      expect(ev.experiment).toBe("EnforcementLagExperiment");
      expect(ev.total).toBe(150);
    }
  });

  it("parses a seed_complete event with a condition dict", () => {
    const parser = new LineParser();
    const events = parser.feed(
      line({
        type: "seed_complete",
        experiment: "EnforcementLagExperiment",
        completed: 7,
        total: 150,
        condition: { lag: 20 },
        seed: 6,
      })
    );
    expect(events).toHaveLength(1);
    const ev = events[0];
    expect(ev?.type).toBe("seed_complete");
    if (ev?.type === "seed_complete") {
      expect(ev.completed).toBe(7);
      expect(ev.condition).toEqual({ lag: 20 });
      expect(ev.seed).toBe(6);
    }
  });

  it("parses multiple events from a single chunk", () => {
    const parser = new LineParser();
    const chunk =
      line({ type: "start", experiment: "GeometryExperiment", total: 360 }) +
      line({
        type: "seed_complete",
        experiment: "GeometryExperiment",
        completed: 1,
        total: 360,
        condition: { geometry: "euclidean", alpha: 0.0 },
        seed: 0,
      });
    const events = parser.feed(chunk);
    expect(events).toHaveLength(2);
    expect(events[0]?.type).toBe("start");
    expect(events[1]?.type).toBe("seed_complete");
  });

  // ── Chunk splitting ───────────────────────────────────────────────────────

  it("reassembles a JSON payload split across two chunks", () => {
    const parser = new LineParser();
    const fullLine = line({
      type: "start",
      experiment: "EnforcementLagExperiment",
      total: 150,
    });

    // Split at an arbitrary byte inside the JSON
    const splitAt = Math.floor(fullLine.length / 2);
    const chunk1 = fullLine.slice(0, splitAt);
    const chunk2 = fullLine.slice(splitAt);

    const events1 = parser.feed(chunk1);
    expect(events1).toHaveLength(0); // incomplete line, nothing yet

    const events2 = parser.feed(chunk2);
    expect(events2).toHaveLength(1);
    expect(events2[0]?.type).toBe("start");
  });

  it("handles a split at the exact newline boundary", () => {
    const parser = new LineParser();
    const payload = JSON.stringify({
      type: "complete",
      experiment: "GeometryExperiment",
      figures: 1,
      rows: 360,
    });
    // Chunk 1: sentinel + payload (no newline)
    const events1 = parser.feed(`${SENTINEL}${payload}`);
    expect(events1).toHaveLength(0);

    // Chunk 2: just the newline
    const events2 = parser.feed("\n");
    expect(events2).toHaveLength(1);
    expect(events2[0]?.type).toBe("complete");
  });

  it("handles many splits across short chunks", () => {
    const parser = new LineParser();
    const fullLine = line({
      type: "error",
      experiment: "lag",
      message: "something went wrong",
    });

    let allEvents: ReturnType<LineParser["feed"]> = [];
    // Feed one character at a time
    for (const char of fullLine) {
      allEvents = [...allEvents, ...parser.feed(char)];
    }
    expect(allEvents).toHaveLength(1);
    expect(allEvents[0]?.type).toBe("error");
  });

  // ── Sentinel filtering ────────────────────────────────────────────────────

  it("ignores prose lines without the sentinel prefix", () => {
    const parser = new LineParser();
    const events = parser.feed(
      prose("Running experiment: lag") +
        prose("============================================================") +
        prose("  ** lag=0  Δ=-0.00251  p=0.0000") +
        prose("CSV  → policyswarm_output/lag/EnforcementLagExperiment_results.csv")
    );
    expect(events).toHaveLength(0);
  });

  it("extracts event from a line that has prose before the sentinel", () => {
    // Should not happen in practice but is handled gracefully
    const parser = new LineParser();
    const json = JSON.stringify({
      type: "start",
      experiment: "OversightPhaseExperiment",
      total: 120,
    });
    const events = parser.feed(`some prefix text ${SENTINEL}${json}\n`);
    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe("start");
  });

  // ── Schema rejection ──────────────────────────────────────────────────────

  it("silently discards valid JSON with an unknown event type", () => {
    const parser = new LineParser();
    const events = parser.feed(
      line({ type: "progress_update", experiment: "lag", pct: 0.5 })
    );
    expect(events).toHaveLength(0);
  });

  it("silently discards valid JSON missing required fields", () => {
    const parser = new LineParser();
    // Missing 'total' on a start event
    const events = parser.feed(
      line({ type: "start", experiment: "GeometryExperiment" })
    );
    expect(events).toHaveLength(0);
  });

  it("silently discards malformed JSON", () => {
    const parser = new LineParser();
    const events = parser.feed(`${SENTINEL}{not valid json}\n`);
    expect(events).toHaveLength(0);
  });

  // ── flush() ───────────────────────────────────────────────────────────────

  it("flush() returns nothing when buffer is empty", () => {
    const parser = new LineParser();
    expect(parser.flush()).toHaveLength(0);
  });

  it("flush() parses a buffered event not followed by a newline", () => {
    const parser = new LineParser();
    const json = JSON.stringify({
      type: "complete",
      experiment: "lag",
      figures: 1,
      rows: 150,
    });
    // Feed without trailing newline — stays in buffer
    const events1 = parser.feed(`${SENTINEL}${json}`);
    expect(events1).toHaveLength(0);

    const flushed = parser.flush();
    expect(flushed).toHaveLength(1);
    expect(flushed[0]?.type).toBe("complete");
  });

  it("flush() clears the buffer so subsequent feeds start fresh", () => {
    const parser = new LineParser();
    parser.feed(`${SENTINEL}{"type":"`); // partial, stuck in buffer
    parser.flush(); // drains and discards malformed partial

    // Now feed a complete valid event — should work without contamination
    const events = parser.feed(
      line({ type: "start", experiment: "lag", total: 150 })
    );
    expect(events).toHaveLength(1);
  });
});
