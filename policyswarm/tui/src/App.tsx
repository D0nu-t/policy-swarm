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
import { Box, Text, useApp, useInput, type Key } from "ink";
import { AppState, ExperimentState, ExperimentStatus } from "./types.js";
import { AppAction } from "./reducer.js";

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const BAR_WIDTH = 20;
const MAX_LOG_DISPLAY = 8;
const NAME_WIDTH = 15;

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function statusIcon(status: ExperimentStatus): string {
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

function statusColor(
  status: ExperimentStatus
): "gray" | "cyan" | "green" | "red" {
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

function progressBar(completed: number, total: number): string {
  if (total <= 0) return "░".repeat(BAR_WIDTH);
  const pct = Math.min(completed / total, 1);
  const filled = Math.round(pct * BAR_WIDTH);
  const empty = BAR_WIDTH - filled;
  return "█".repeat(filled) + "░".repeat(empty);
}

function elapsedStr(startedAt: number): string {
  const secs = Math.floor((Date.now() - startedAt) / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

interface ExperimentRowProps {
  exp: ExperimentState;
}

function ExperimentRow({ exp }: ExperimentRowProps): React.ReactElement {
  const color = statusColor(exp.status);
  const icon = statusIcon(exp.status);
  const bar = progressBar(exp.completed, exp.total);

  const counter =
    exp.status === "pending"
      ? "─".repeat(8)
      : `${String(exp.completed).padStart(4)}/${String(exp.total).padStart(4)}`;

  const condStr =
    exp.lastCondition !== null
      ? Object.entries(exp.lastCondition)
          .map(([k, v]) => `${k}=${v}`)
          .join(" ")
      : "";

  return (
    <Box>
      {/* icon */}
      <Text color={color}>{icon} </Text>

      {/* name, left-padded to NAME_WIDTH */}
      <Text color={exp.status === "pending" ? "gray" : "white"}>
        {exp.shortName.padEnd(NAME_WIDTH)}
      </Text>

      {/* progress bar */}
      <Text color={color}>[{bar}] </Text>

      {/* counter */}
      <Text color={exp.status === "pending" ? "gray" : "white"}>
        {counter}{"  "}
      </Text>

      {/* condition hint for running experiments */}
      {exp.status === "running" && condStr.length > 0 && (
        <Text color="gray" dimColor>
          {condStr}
        </Text>
      )}

      {/* error message */}
      {exp.status === "error" && exp.errorMessage !== null && (
        <Text color="red"> {exp.errorMessage.slice(0, 60)}</Text>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Root App
// ---------------------------------------------------------------------------

export interface AppProps {
  state: AppState;
  dispatch: (action: AppAction) => void;
  seeds: number[];
}

export function App({ state, seeds }: AppProps): React.ReactElement {
  const { exit } = useApp();

  // q or Ctrl+C exits
  useInput((input: string, key: Key) => {
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

  const completedCount = state.experiments.filter(
    (e) => e.status === "complete"
  ).length;
  const errorCount = state.experiments.filter(
    (e) => e.status === "error"
  ).length;

  const logLines = state.log.slice(-MAX_LOG_DISPLAY);

  return (
    <Box flexDirection="column" padding={1}>
      {/* ── Header ───────────────────────────────────────────────── */}
      <Box marginBottom={1}>
        <Text bold color="cyan">
          PolicySwarm TUI{"  "}
        </Text>
        <Text color="gray">
          S={seeds.length} seeds · {completedCount}/6 done
          {errorCount > 0 && (
            <Text color="red">  {errorCount} failed</Text>
          )}
          {"  "}⏱ {elapsedStr(state.startedAt)}
        </Text>
      </Box>

      {/* ── Divider ──────────────────────────────────────────────── */}
      <Text color="gray">{"─".repeat(60)}</Text>

      {/* ── Experiment rows ──────────────────────────────────────── */}
      <Box flexDirection="column" marginTop={1} marginBottom={1}>
        {state.experiments.map((exp) => (
          <ExperimentRow key={exp.shortName} exp={exp} />
        ))}
      </Box>

      {/* ── Divider ──────────────────────────────────────────────── */}
      <Text color="gray">{"─".repeat(60)}</Text>

      {/* ── Log pane ─────────────────────────────────────────────── */}
      <Box flexDirection="column" marginTop={1}>
        <Text bold color="gray">
          Log
        </Text>
        {logLines.length === 0 ? (
          <Text color="gray" dimColor>
            waiting for output…
          </Text>
        ) : (
          logLines.map((line, i) => (
            <Text key={i} color="gray" dimColor wrap="truncate">
              {"> "}
              {line}
            </Text>
          ))
        )}
      </Box>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <Box marginTop={1}>
        {state.runComplete ? (
          <Text color={errorCount > 0 ? "red" : "green"}>
            {errorCount > 0
              ? `Finished with ${errorCount} error(s). Exit code: ${state.exitCode ?? "?"}`
              : "All experiments complete."}
          </Text>
        ) : (
          <Text color="gray" dimColor>
            Press q to exit early
          </Text>
        )}
      </Box>
    </Box>
  );
}
