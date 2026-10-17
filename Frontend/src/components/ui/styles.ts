/**
 * Tailwind class strings for patterns used across the app. Plain strings (not components)
 * so they apply to any element: <button className={button()}>, <Link className={button("primary")}>.
 */

/** Join class names, skipping falsy ones: cx("a", isOn && "b"). */
export const cx = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(" ");

const focusRing = "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent";

type ButtonVariant = "default" | "primary" | "danger";

/** Buttons and button-styled links. `icon`: square, icon only. `block`: full width. */
export function button(variant: ButtonVariant = "default", { icon = false, block = false } = {}) {
  return cx(
    "inline-flex cursor-pointer items-center gap-1.5 rounded-lg border font-medium hover:no-underline",
    "disabled:cursor-not-allowed disabled:opacity-50",
    focusRing,
    variant === "primary"
      ? "border-transparent bg-accent text-white hover:bg-accent-ink"
      : "border-line bg-surface hover:bg-surface-2",
    variant === "danger" && "text-critical",
    icon ? "p-1.75 [&_svg]:block [&_svg]:size-4.5" : block ? "w-full justify-center px-3 py-2.5" : "px-3 py-1.75",
  );
}

/** Text inputs and selects. Invalid fields (aria-invalid) get a red border. */
export const control = cx(
  "min-w-0 rounded-lg border border-line bg-surface px-2.5 py-1.75 aria-[invalid=true]:border-critical",
  "focus:outline-2 focus:outline-offset-1 focus:outline-accent",
);
export const textarea = cx(control, "min-h-18 w-full resize-y");

/** Raised panel. Add `cardPad` for the standard padding. */
export const card = "rounded-card border border-line bg-surface shadow-card";
export const cardPad = "px-5 py-4.5";

/** Label above a form control. */
export const fieldLabel = "text-sm text-muted";

/** Rounded pill with a coloured dot, e.g. a potential band. */
export const badge =
  "inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2 py-0.5 text-label font-semibold whitespace-nowrap text-fg-2";

/** Small outlined tag, e.g. a pipeline stage. */
export const chip = "rounded-md border border-line px-1.75 py-px text-xs whitespace-nowrap text-fg-2";

/** Toggle button in a group (multi-select). */
export const toggle = cx(
  "cursor-pointer rounded-full border border-line bg-surface px-2.5 py-1 text-ctl text-fg-2 hover:bg-surface-2",
  "aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-white",
);

/** Two-column form layout (one column on phones); `col-span-full` for wide fields. */
export const formGrid = "grid grid-cols-2 gap-x-3.5 gap-y-3 max-sm:grid-cols-1";

/** Collapsible framework section (<details> + <summary>); consecutive ones are spaced. */
export const disclosure = "rounded-lg border border-grid px-3.5 py-2.5 [&+&]:mt-2";
export const disclosureSummary = "flex cursor-pointer justify-between gap-2 font-semibold";

/** Square tag for an Ocean Impact Navigator area code (A-F). */
export const areaCode = "mr-2 inline-grid size-5.5 place-items-center rounded-md bg-surface-2 text-label font-bold";

/** Common layouts. */
export const stack = "flex flex-col gap-4";
export const row = "flex flex-wrap items-center gap-2";

/** Data tables: header and body cells. Body rows separate with a grid line, except the last. */
export const table = "w-full border-collapse [&_tbody_tr:last-child>td]:border-b-0";
export const th =
  "border-b border-grid px-3 py-2.5 text-left text-label font-semibold tracking-[0.03em] whitespace-nowrap text-muted uppercase";
export const td = "border-b border-grid p-3 align-middle";
export const num = "text-right tabular-nums";
