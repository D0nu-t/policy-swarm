/**
 * reducer.ts
 * ----------
 * Pure state reducer: (AppState, action) => AppState.
 *
 * "Pure" here means no side effects and no mutation of the input state —
 * every branch returns a new object. This makes the reducer trivially
 * testable with Vitest: feed in a state and an event, assert the output.
 *
 * Class-name normalisation
 * ------------------------
 * start / seed_complete / complete events carry the Python class name
 * (e.g. "EnforcementLagExperiment") while error events from the
 * PolicySwarm.run_all() wrapper carry the short name ("lag"). The reducer
 * normalises both using CLASS_TO_SHORT so all downstream rendering code
 * works with short names only.
 */
import { AppState, ExperimentEvent } from "./types.js";
/** All six experiments in run_all.py execution order. */
export declare const EXPERIMENT_ORDER: readonly ["oversight", "lag", "media", "counterfactual", "centrality", "geometry"];
export type ShortName = (typeof EXPERIMENT_ORDER)[number];
export declare function initialState(): AppState;
export type AppAction = {
    kind: "event";
    event: ExperimentEvent;
} | {
    kind: "log";
    line: string;
} | {
    kind: "process_exit";
    code: number | null;
};
export declare function reducer(state: AppState, action: AppAction): AppState;
