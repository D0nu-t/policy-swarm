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
// ---------------------------------------------------------------------------
// Experiment registry — keeps reducer in sync with Python experiment list
// ---------------------------------------------------------------------------
/** All six experiments in run_all.py execution order. */
export const EXPERIMENT_ORDER = [
    "oversight",
    "lag",
    "media",
    "counterfactual",
    "centrality",
    "geometry",
];
/** Maps Python class name → short CLI name. */
const CLASS_TO_SHORT = {
    OversightPhaseExperiment: "oversight",
    EnforcementLagExperiment: "lag",
    MediaInteractionExperiment: "media",
    CounterfactualShockExperiment: "counterfactual",
    CentralitySweepExperiment: "centrality",
    GeometryExperiment: "geometry",
};
/** Maps short name → Python class name. */
const SHORT_TO_CLASS = {
    oversight: "OversightPhaseExperiment",
    lag: "EnforcementLagExperiment",
    media: "MediaInteractionExperiment",
    counterfactual: "CounterfactualShockExperiment",
    centrality: "CentralitySweepExperiment",
    geometry: "GeometryExperiment",
};
/**
 * Resolve an experiment identifier (class name or short name) to its short
 * name. Returns null if the identifier is not recognised.
 */
function resolveShortName(id) {
    if (id in CLASS_TO_SHORT) {
        return CLASS_TO_SHORT[id] ?? null;
    }
    if (id in SHORT_TO_CLASS) {
        return id;
    }
    return null;
}
// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------
function makeExperimentState(shortName) {
    return {
        shortName,
        className: SHORT_TO_CLASS[shortName] ?? shortName,
        status: "pending",
        completed: 0,
        total: 0,
        figures: 0,
        errorMessage: null,
        lastCondition: null,
        lastSeed: null,
    };
}
export function initialState() {
    return {
        experiments: EXPERIMENT_ORDER.map(makeExperimentState),
        log: [],
        runComplete: false,
        exitCode: null,
        startedAt: Date.now(),
    };
}
// ---------------------------------------------------------------------------
// Helper: update a single experiment by short name
// ---------------------------------------------------------------------------
const MAX_LOG_LINES = 200;
function updateExperiment(experiments, shortName, updater) {
    return experiments.map((exp) => exp.shortName === shortName ? updater(exp) : exp);
}
export function reducer(state, action) {
    switch (action.kind) {
        // -----------------------------------------------------------------------
        case "event": {
            const ev = action.event;
            const shortName = resolveShortName(ev.experiment);
            // Unknown experiment identifier: append to log and ignore
            if (shortName === null) {
                return {
                    ...state,
                    log: trimLog([
                        ...state.log,
                        `[unknown experiment] ${JSON.stringify(ev)}`,
                    ]),
                };
            }
            switch (ev.type) {
                case "start":
                    return {
                        ...state,
                        experiments: updateExperiment(state.experiments, shortName, (prev) => ({
                            ...prev,
                            status: "running",
                            total: ev.total,
                            completed: 0,
                        })),
                    };
                case "seed_complete":
                    return {
                        ...state,
                        experiments: updateExperiment(state.experiments, shortName, (prev) => ({
                            ...prev,
                            status: "running",
                            completed: ev.completed,
                            total: ev.total,
                            lastCondition: ev.condition,
                            lastSeed: ev.seed,
                        })),
                    };
                case "complete":
                    return {
                        ...state,
                        experiments: updateExperiment(state.experiments, shortName, (prev) => ({
                            ...prev,
                            status: "complete",
                            completed: prev.total,
                            figures: ev.figures,
                        })),
                    };
                case "error":
                    return {
                        ...state,
                        experiments: updateExperiment(state.experiments, shortName, (prev) => ({
                            ...prev,
                            status: "error",
                            errorMessage: ev.message,
                        })),
                    };
            }
            // TypeScript exhaustiveness: the discriminated union above covers all
            // cases in ExperimentEvent, but this satisfies the compiler.
            return state;
        }
        // -----------------------------------------------------------------------
        case "log": {
            return {
                ...state,
                log: trimLog([...state.log, action.line]),
            };
        }
        // -----------------------------------------------------------------------
        case "process_exit": {
            return {
                ...state,
                runComplete: true,
                exitCode: action.code,
            };
        }
    }
}
function trimLog(lines) {
    return lines.length > MAX_LOG_LINES
        ? lines.slice(lines.length - MAX_LOG_LINES)
        : lines;
}
