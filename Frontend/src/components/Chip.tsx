import type { ReactNode } from "react";

/**
 * Chip colours, shared so the same colour means the same thing everywhere:
 * warning = only claimed or weak, info and primary = backed by evidence or data,
 * success = verified or strong, danger = early or failing, neutral = nothing known.
 */
export type ChipTone = "neutral" | "info" | "primary" | "success" | "warning" | "danger";

export function Chip({ tone = "neutral", title, children }: { tone?: ChipTone; title?: string; children: ReactNode }) {
  return (
    <span className={`chip tone-${tone}`} title={title}>
      {children}
    </span>
  );
}

/** Ocean Impact Navigator evidence, 0-4: none, claimed, evidenced, measured, verified. */
export const EVIDENCE_TONES: ChipTone[] = ["neutral", "warning", "info", "primary", "success"];

/** How sure a fact is: verified (registry, filing or funder), claimed (company or aggregator), inferred. */
export const STATUS_TONES: Record<string, ChipTone> = { verified: "success", claimed: "warning", inferred: "neutral" };

/** Investment potential bands, as on the grade circle. */
export const BAND_TONES: Record<string, ChipTone> = { Strong: "success", Promising: "info", Watch: "warning", Early: "danger" };
