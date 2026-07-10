/**
 * App.tsx
 * -------
 * Root Ink component. Renders:
 *   - Header with seed count and elapsed time
 *   - One row per experiment: icon + name + progress bar + counter + status
 *   - Scrollable log pane (last N lines of raw stdout)
 *   - Footer with keybinding hints
 *
 * The component owns no state itself; it receives AppState as a prop and
 * dispatches actions via the dispatch prop. Side effects (spawning the child
 * process) live in index.tsx so this file stays purely presentational and
 * testable without a running Python process.
 */
import React from "react";
import { AppState } from "./types.js";
import { AppAction } from "./reducer.js";
export interface AppProps {
    state: AppState;
    dispatch: (action: AppAction) => void;
    seeds: number[];
}
export declare function App({ state, seeds }: AppProps): React.ReactElement;
