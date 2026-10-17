export function compactMoney(value: number | null | undefined, currency = "USD"): string {
  if (value == null) return "Undisclosed";
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function score(value: number): string {
  return Math.round(value).toString();
}

const STAGE_LABELS: Record<string, string> = {
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
  "series-b": "Series B",
  "series-c+": "Series C+",
  growth: "Growth",
  "project-finance": "Project finance",
  grant: "Grant",
};

/** Human label for a funding stage or round type slug, e.g. "series-a" → "Series A". */
export function stageLabel(slug: string): string {
  return STAGE_LABELS[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1).replace(/-/g, " ");
}

export function partialDate(value: string | null): string {
  if (!value) return "Date unknown";
  const [y, m] = value.split("-");
  if (!m) return y;
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString("en", { month: "short", year: "numeric" });
}

export const PIPELINE_LABELS: Record<string, string> = {
  sourced: "Sourced",
  screening: "Screening",
  diligence: "Due diligence",
  "term-sheet": "Term sheet",
  portfolio: "Portfolio",
  passed: "Passed",
};
