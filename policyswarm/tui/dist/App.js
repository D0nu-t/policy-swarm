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
import { Box, Text, useApp, useInput } from "ink";
// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------
const BAR_WIDTH = 20;
const MAX_LOG_DISPLAY = 8;
const NAME_WIDTH = 15;
// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function statusIcon(status) {
    switch (status) {
        case "pending":
            return "○";
        case "running":
            return "●";
        case "complete":
            return "✓";
        case "error":
            return "✗";
    }
}
function statusColor(status) {
    switch (status) {
        case "pending":
            return "gray";
        case "running":
            return "cyan";
        case "complete":
            return "green";
        case "error":
            return "red";
    }
}
function progressBar(completed, total) {
    if (total <= 0)
        return "░".repeat(BAR_WIDTH);
    const pct = Math.min(completed / total, 1);
    const filled = Math.round(pct * BAR_WIDTH);
    const empty = BAR_WIDTH - filled;
    return "█".repeat(filled) + "░".repeat(empty);
}
function elapsedStr(startedAt) {
    const secs = Math.floor((Date.now() - startedAt) / 1000);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}m ${s.toString().padStart(2, "0")}s`;
}
function ExperimentRow({ exp }) {
    const color = statusColor(exp.status);
    const icon = statusIcon(exp.status);
    const bar = progressBar(exp.completed, exp.total);
    const counter = exp.status === "pending"
        ? "─".repeat(8)
        : `${String(exp.completed).padStart(4)}/${String(exp.total).padStart(4)}`;
    const condStr = exp.lastCondition !== null
        ? Object.entries(exp.lastCondition)
            .map(([k, v]) => `${k}=${v}`)
            .join(" ")
        : "";
    return (React.createElement(Box, null,
        React.createElement(Text, { color: color },
            icon,
            " "),
        React.createElement(Text, { color: exp.status === "pending" ? "gray" : "white" }, exp.shortName.padEnd(NAME_WIDTH)),
        React.createElement(Text, { color: color },
            "[",
            bar,
            "] "),
        React.createElement(Text, { color: exp.status === "pending" ? "gray" : "white" },
            counter,
            "  "),
        exp.status === "running" && condStr.length > 0 && (React.createElement(Text, { color: "gray", dimColor: true }, condStr)),
        exp.status === "error" && exp.errorMessage !== null && (React.createElement(Text, { color: "red" },
            " ",
            exp.errorMessage.slice(0, 60)))));
}
export function App({ state, seeds }) {
    const { exit } = useApp();
    // q or Ctrl+C exits
    useInput((input, key) => {
        if (input === "q" || key.escape) {
            exit();
        }
    });
    // Auto-exit cleanly after the run completes
    React.useEffect(() => {
        if (state.runComplete) {
            // Give Ink one render cycle to display the final state
            const t = setTimeout(() => exit(), 150);
            return () => clearTimeout(t);
        }
        return undefined;
    }, [state.runComplete, exit]);
    const completedCount = state.experiments.filter((e) => e.status === "complete").length;
    const errorCount = state.experiments.filter((e) => e.status === "error").length;
    const logLines = state.log.slice(-MAX_LOG_DISPLAY);
    return (React.createElement(Box, { flexDirection: "column", padding: 1 },
        React.createElement(Box, { marginBottom: 1 },
            React.createElement(Text, { bold: true, color: "cyan" },
                "PolicySwarm TUI",
                "  "),
            React.createElement(Text, { color: "gray" },
                "S=",
                seeds.length,
                " seeds \u00B7 ",
                completedCount,
                "/6 done",
                errorCount > 0 && (React.createElement(Text, { color: "red" },
                    "  ",
                    errorCount,
                    " failed")),
                "  ",
                "\u23F1 ",
                elapsedStr(state.startedAt))),
        React.createElement(Text, { color: "gray" }, "─".repeat(60)),
        React.createElement(Box, { flexDirection: "column", marginTop: 1, marginBottom: 1 }, state.experiments.map((exp) => (React.createElement(ExperimentRow, { key: exp.shortName, exp: exp })))),
        React.createElement(Text, { color: "gray" }, "─".repeat(60)),
        React.createElement(Box, { flexDirection: "column", marginTop: 1 },
            React.createElement(Text, { bold: true, color: "gray" }, "Log"),
            logLines.length === 0 ? (React.createElement(Text, { color: "gray", dimColor: true }, "waiting for output\u2026")) : (logLines.map((line, i) => (React.createElement(Text, { key: i, color: "gray", dimColor: true, wrap: "truncate" },
                "> ",
                line))))),
        React.createElement(Box, { marginTop: 1 }, state.runComplete ? (React.createElement(Text, { color: errorCount > 0 ? "red" : "green" }, errorCount > 0
            ? `Finished with ${errorCount} error(s). Exit code: ${state.exitCode ?? "?"}`
            : "All experiments complete.")) : (React.createElement(Text, { color: "gray", dimColor: true }, "Press q to exit early")))));
}
