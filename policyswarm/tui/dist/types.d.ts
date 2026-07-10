/**
 * types.ts
 * --------
 * Single source of truth for the event protocol between the Python process
 * and the TUI. Every structured event emitted by Python (via ##EVENT## prefix)
 * must match one of the schemas here before it enters the reducer.
 *
 * The discriminated union on `type` means TypeScript narrows correctly in
 * switch statements in the reducer — no casts, no `any`.
 */
import { z } from "zod";
declare const ConditionSchema: z.ZodRecord<z.ZodString, z.ZodUnion<[z.ZodString, z.ZodNumber, z.ZodBoolean]>>;
export type Condition = z.infer<typeof ConditionSchema>;
/** Fired once per experiment at the start of run(), carries total unit count. */
export declare const StartEventSchema: z.ZodObject<{
    type: z.ZodLiteral<"start">;
    experiment: z.ZodString;
    total: z.ZodNumber;
}, "strip", z.ZodTypeAny, {
    type: "start";
    experiment: string;
    total: number;
}, {
    type: "start";
    experiment: string;
    total: number;
}>;
/** Fired after each (seed × condition) iteration inside run(). */
export declare const SeedCompleteEventSchema: z.ZodObject<{
    type: z.ZodLiteral<"seed_complete">;
    experiment: z.ZodString;
    completed: z.ZodNumber;
    total: z.ZodNumber;
    condition: z.ZodRecord<z.ZodString, z.ZodUnion<[z.ZodString, z.ZodNumber, z.ZodBoolean]>>;
    seed: z.ZodNumber;
}, "strip", z.ZodTypeAny, {
    type: "seed_complete";
    experiment: string;
    total: number;
    completed: number;
    condition: Record<string, string | number | boolean>;
    seed: number;
}, {
    type: "seed_complete";
    experiment: string;
    total: number;
    completed: number;
    condition: Record<string, string | number | boolean>;
    seed: number;
}>;
/** Fired by report() after analyse() and plot() finish successfully. */
export declare const CompleteEventSchema: z.ZodObject<{
    type: z.ZodLiteral<"complete">;
    experiment: z.ZodString;
    figures: z.ZodNumber;
    rows: z.ZodNumber;
}, "strip", z.ZodTypeAny, {
    type: "complete";
    experiment: string;
    figures: number;
    rows: number;
}, {
    type: "complete";
    experiment: string;
    figures: number;
    rows: number;
}>;
/**
 * Fired on exception inside PolicySwarm.run_all() or
 * _run_with_prebuilt_policy(). The `experiment` field may be either a
 * short name ("lag") or a class name ("EnforcementLagExperiment") depending
 * on which code path raised; the reducer normalises both.
 */
export declare const ErrorEventSchema: z.ZodObject<{
    type: z.ZodLiteral<"error">;
    experiment: z.ZodString;
    message: z.ZodString;
}, "strip", z.ZodTypeAny, {
    message: string;
    type: "error";
    experiment: string;
}, {
    message: string;
    type: "error";
    experiment: string;
}>;
/** Top-level discriminated union. */
export declare const ExperimentEventSchema: z.ZodDiscriminatedUnion<"type", [z.ZodObject<{
    type: z.ZodLiteral<"start">;
    experiment: z.ZodString;
    total: z.ZodNumber;
}, "strip", z.ZodTypeAny, {
    type: "start";
    experiment: string;
    total: number;
}, {
    type: "start";
    experiment: string;
    total: number;
}>, z.ZodObject<{
    type: z.ZodLiteral<"seed_complete">;
    experiment: z.ZodString;
    completed: z.ZodNumber;
    total: z.ZodNumber;
    condition: z.ZodRecord<z.ZodString, z.ZodUnion<[z.ZodString, z.ZodNumber, z.ZodBoolean]>>;
    seed: z.ZodNumber;
}, "strip", z.ZodTypeAny, {
    type: "seed_complete";
    experiment: string;
    total: number;
    completed: number;
    condition: Record<string, string | number | boolean>;
    seed: number;
}, {
    type: "seed_complete";
    experiment: string;
    total: number;
    completed: number;
    condition: Record<string, string | number | boolean>;
    seed: number;
}>, z.ZodObject<{
    type: z.ZodLiteral<"complete">;
    experiment: z.ZodString;
    figures: z.ZodNumber;
    rows: z.ZodNumber;
}, "strip", z.ZodTypeAny, {
    type: "complete";
    experiment: string;
    figures: number;
    rows: number;
}, {
    type: "complete";
    experiment: string;
    figures: number;
    rows: number;
}>, z.ZodObject<{
    type: z.ZodLiteral<"error">;
    experiment: z.ZodString;
    message: z.ZodString;
}, "strip", z.ZodTypeAny, {
    message: string;
    type: "error";
    experiment: string;
}, {
    message: string;
    type: "error";
    experiment: string;
}>]>;
export type StartEvent = z.infer<typeof StartEventSchema>;
export type SeedCompleteEvent = z.infer<typeof SeedCompleteEventSchema>;
export type CompleteEvent = z.infer<typeof CompleteEventSchema>;
export type ErrorEvent = z.infer<typeof ErrorEventSchema>;
export type ExperimentEvent = z.infer<typeof ExperimentEventSchema>;
export type ExperimentStatus = "pending" | "running" | "complete" | "error";
export interface ExperimentState {
    /** Short name used by CLI / run_all.py, e.g. "lag". */
    shortName: string;
    /** Python class name, e.g. "EnforcementLagExperiment". */
    className: string;
    status: ExperimentStatus;
    completed: number;
    total: number;
    figures: number;
    errorMessage: string | null;
    /** Most recent condition dict seen in a seed_complete event. */
    lastCondition: Condition | null;
    lastSeed: number | null;
}
export interface AppState {
    experiments: ExperimentState[];
    /** Rolling log of raw stdout lines (prose + events interleaved). */
    log: string[];
    /** True once the Python process has exited. */
    runComplete: boolean;
    /** Exit code from the Python process, null until exited. */
    exitCode: number | null;
    startedAt: number;
}
export {};
