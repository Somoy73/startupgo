export const PIPELINE_LABELS = {
  sourced: "Sourced",
  screening: "Screening",
  diligence: "Diligence",
  "term-sheet": "Term sheet",
  invested: "Invested",
  portfolio: "Portfolio",
  passed: "Passed",
};
export const score = (n: number) => Math.round(n);
export const compactMoney = (n: number | null, currency = "USD") =>
  n == null
    ? "Undisclosed"
    : `${currency === "USD" ? "$" : currency + " "}${n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : n}`;
export const partialDate = (d: string | null) => d || "Undisclosed";
export const stageLabel = (s: string) =>
  s.charAt(0).toUpperCase() + s.slice(1).replaceAll("-", " ");
