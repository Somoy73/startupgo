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

export function titleCase(slug: string): string {
  return slug
    .split("-")
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
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
