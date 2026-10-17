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
const SYMBOLS: Record<string, string> = { EUR: "€", USD: "$", GBP: "£" };
/** €25M, $1.2M, £350K, NOK 40M. Amounts are shown in euros unless a currency is given. */
export const compactMoney = (n: number | null, currency = "EUR") =>
  n == null
    ? "Undisclosed"
    : `${SYMBOLS[currency.toUpperCase()] ?? currency + " "}${n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : Math.round(n)}`;

// Approximate static FX to USD, as in Backend/app/scoring.py (FX_TO_USD).
const FX_TO_USD: Record<string, number> = { USD: 1, EUR: 1.08, GBP: 1.27, NOK: 0.093, DKK: 0.145 };
/** An amount in euros at approximate rates; null when the amount or its currency's rate is unknown. */
export function toEur(amount: number | null, currency: string | null): number | null {
  const rate = currency ? FX_TO_USD[currency.toUpperCase()] : undefined;
  return amount == null || rate === undefined ? null : (amount * rate) / FX_TO_USD["EUR"]!;
}
export const partialDate = (d: string | null) => d || "Undisclosed";
export const stageLabel = (s: string) =>
  s.charAt(0).toUpperCase() + s.slice(1).replaceAll("-", " ");
