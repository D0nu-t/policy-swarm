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
// ---------------------------------------------------------------------------
// Condition record: freeform dict of condition variable values
// e.g. { lag: 20 }, { geometry: "cosine", lag: 40 }
// ---------------------------------------------------------------------------
const ConditionSchema = z.record(z.union([z.string(), z.number(), z.boolean()]));
// ---------------------------------------------------------------------------
// Individual event schemas
// ---------------------------------------------------------------------------
/** Fired once per experiment at the start of run(), carries total unit count. */
export const StartEventSchema = z.object({
    type: z.literal("start"),
    experiment: z.string().min(1),
    total: z.number().int().positive(),
});
/** Fired after each (seed × condition) iteration inside run(). */
export const SeedCompleteEventSchema = z.object({
    type: z.literal("seed_complete"),
    experiment: z.string().min(1),
    completed: z.number().int().nonnegative(),
    total: z.number().int().positive(),
    condition: ConditionSchema,
    seed: z.number().int().nonnegative(),
});
/** Fired by report() after analyse() and plot() finish successfully. */
export const CompleteEventSchema = z.object({
    type: z.literal("complete"),
    experiment: z.string().min(1),
    figures: z.number().int().nonnegative(),
    rows: z.number().int().nonnegative(),
});
/**
 * Fired on exception inside PolicySwarm.run_all() or
 * _run_with_prebuilt_policy(). The `experiment` field may be either a
 * short name ("lag") or a class name ("EnforcementLagExperiment") depending
 * on which code path raised; the reducer normalises both.
 */
export const ErrorEventSchema = z.object({
    type: z.literal("error"),
    experiment: z.string().min(1),
    message: z.string(),
});
/** Top-level discriminated union. */
export const ExperimentEventSchema = z.discriminatedUnion("type", [
    StartEventSchema,
    SeedCompleteEventSchema,
    CompleteEventSchema,
    ErrorEventSchema,
]);
