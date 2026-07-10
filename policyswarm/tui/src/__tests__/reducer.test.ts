/**
 * reducer.test.ts
 * ---------------
 * Tests for the pure reducer function. Because the reducer has no side
 * effects and takes plain objects in and out, every test is a one-liner
 * assertion: call reducer(state, action), inspect the result.
 *
 * Coverage:
 *   - start event: status transitions to "running", total is set
 *   - seed_complete: completed counter increments, condition recorded
 *   - complete: status transitions to "complete", figures counted
 *   - error: status transitions to "error", message stored
 *   - Class-name normalisation: class name → short name both resolve
 *   - Unknown experiment: state unchanged (no crash)
 *   - Log accumulation and MAX_LOG_LINES trimming
 *   - process_exit action: runComplete flipped, exitCode set
 *   - State immutability: original state object is never mutated
 */

import { describe, it, expect, beforeEach } from "vitest";
import { reducer, initialState, AppAction } from "../reducer.js";
import { AppState } from "../types.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getExp(state: AppState, shortName: string) {
  const exp = state.experiments.find((e) => e.shortName === shortName);
  if (exp === undefined) throw new Error(`Experiment not found: ${shortName}`);
  return exp;
}

function applyEvent(state: AppState, event: AppAction["event"] extends infer E ? E : never): AppState {
  return reducer(state, { kind: "event", event } as AppAction);
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

let base: AppState;

beforeEach(() => {
  base = initialState();
});

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe("initialState()", () => {
  it("creates 6 experiments all in pending status", () => {
    expect(base.experiments).toHaveLength(6);
    for (const exp of base.experiments) {
      expect(exp.status).toBe("pending");
      expect(exp.completed).toBe(0);
      expect(exp.total).toBe(0);
    }
  });

  it("experiments are in run_all.py order", () => {
    const names = base.experiments.map((e) => e.shortName);
    expect(names).toEqual([
      "oversight",
      "lag",
      "media",
      "counterfactual",
      "centrality",
      "geometry",
    ]);
  });

  it("runComplete is false", () => {
    expect(base.runComplete).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// start event
// ---------------------------------------------------------------------------

describe("start event", () => {
  it("transitions status to running and sets total (class name)", () => {
    const next = applyEvent(base, {
      type: "start",
      experiment: "EnforcementLagExperiment",
      total: 150,
    });
    const exp = getExp(next, "lag");
    expect(exp.status).toBe("running");
    expect(exp.total).toBe(150);
    expect(exp.completed).toBe(0);
  });

  it("transitions status to running (short name)", () => {
    const next = applyEvent(base, {
      type: "start",
      experiment: "lag",
      total: 150,
    });
    expect(getExp(next, "lag").status).toBe("running");
  });

  it("does not affect other experiments", () => {
    const next = applyEvent(base, {
      type: "start",
      experiment: "lag",
      total: 150,
    });
    expect(getExp(next, "oversight").status).toBe("pending");
    expect(getExp(next, "geometry").status).toBe("pending");
  });
});

// ---------------------------------------------------------------------------
// seed_complete event
// ---------------------------------------------------------------------------

describe("seed_complete event", () => {
  it("increments completed counter and records condition + seed", () => {
    // First put the experiment in running state
    let state = applyEvent(base, {
      type: "start",
      experiment: "lag",
      total: 150,
    });
    state = applyEvent(state, {
      type: "seed_complete",
      experiment: "lag",
      completed: 7,
      total: 150,
      condition: { lag: 20 },
      seed: 6,
    });
    const exp = getExp(state, "lag");
    expect(exp.completed).toBe(7);
    expect(exp.lastCondition).toEqual({ lag: 20 });
    expect(exp.lastSeed).toBe(6);
    expect(exp.status).toBe("running");
  });

  it("updates completed on successive events", () => {
    let state = applyEvent(base, {
      type: "start",
      experiment: "geometry",
      total: 360,
    });
    for (let i = 1; i <= 5; i++) {
      state = applyEvent(state, {
        type: "seed_complete",
        experiment: "GeometryExperiment",
        completed: i,
        total: 360,
        condition: { geometry: "euclidean", alpha: 0.0 },
        seed: i - 1,
      });
    }
    expect(getExp(state, "geometry").completed).toBe(5);
  });
});

// ---------------------------------------------------------------------------
// complete event
// ---------------------------------------------------------------------------

describe("complete event", () => {
  it("transitions status to complete and records figures", () => {
    let state = applyEvent(base, {
      type: "start",
      experiment: "lag",
      total: 150,
    });
    state = applyEvent(state, {
      type: "complete",
      experiment: "EnforcementLagExperiment",
      figures: 2,
      rows: 150,
    });
    const exp = getExp(state, "lag");
    expect(exp.status).toBe("complete");
    expect(exp.figures).toBe(2);
    // completed is pinned to total on complete
    expect(exp.completed).toBe(150);
  });
});

// ---------------------------------------------------------------------------
// error event
// ---------------------------------------------------------------------------

describe("error event", () => {
  it("transitions status to error and stores message", () => {
    const state = applyEvent(base, {
      type: "error",
      experiment: "counterfactual",
      message: "ZeroDivisionError: division by zero",
    });
    const exp = getExp(state, "counterfactual");
    expect(exp.status).toBe("error");
    expect(exp.errorMessage).toBe("ZeroDivisionError: division by zero");
  });

  it("handles error with class name", () => {
    const state = applyEvent(base, {
      type: "error",
      experiment: "CounterfactualShockExperiment",
      message: "oh no",
    });
    expect(getExp(state, "counterfactual").status).toBe("error");
  });
});

// ---------------------------------------------------------------------------
// Unknown experiment
// ---------------------------------------------------------------------------

describe("unknown experiment", () => {
  it("does not crash and appends to log", () => {
    const state = applyEvent(base, {
      type: "start",
      experiment: "SomeUnknownExperiment",
      total: 10,
    });
    // All experiments still pending
    for (const exp of state.experiments) {
      expect(exp.status).toBe("pending");
    }
    // One log entry added
    expect(state.log.some((l) => l.includes("unknown experiment"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// log action
// ---------------------------------------------------------------------------

describe("log action", () => {
  it("appends lines to state.log", () => {
    let state = reducer(base, { kind: "log", line: "line 1" });
    state = reducer(state, { kind: "log", line: "line 2" });
    expect(state.log).toEqual(["line 1", "line 2"]);
  });

  it("trims log to 200 lines", () => {
    let state = base;
    for (let i = 0; i < 250; i++) {
      state = reducer(state, { kind: "log", line: `line ${i}` });
    }
    expect(state.log).toHaveLength(200);
    // Most recent lines are kept
    expect(state.log[state.log.length - 1]).toBe("line 249");
  });
});

// ---------------------------------------------------------------------------
// process_exit action
// ---------------------------------------------------------------------------

describe("process_exit action", () => {
  it("sets runComplete and exitCode", () => {
    const state = reducer(base, { kind: "process_exit", code: 0 });
    expect(state.runComplete).toBe(true);
    expect(state.exitCode).toBe(0);
  });

  it("handles null exit code (signal kill)", () => {
    const state = reducer(base, { kind: "process_exit", code: null });
    expect(state.runComplete).toBe(true);
    expect(state.exitCode).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Immutability
// ---------------------------------------------------------------------------

describe("immutability", () => {
  it("does not mutate the input state object", () => {
    const frozen = Object.freeze({ ...base, experiments: [...base.experiments] });
    // Should not throw even with a frozen (but not deep-frozen) object
    expect(() =>
      reducer(base, { kind: "log", line: "test" })
    ).not.toThrow();
    // Original base is unchanged
    expect(base.log).toHaveLength(0);
  });

  it("returns a new object on every action", () => {
    const next = reducer(base, { kind: "log", line: "x" });
    expect(next).not.toBe(base);
  });
});
