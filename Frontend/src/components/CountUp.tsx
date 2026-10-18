import { useCountUp } from "../lib/useCountUp";

/**
 * A number that counts up to `value` when it appears. Screen readers get the final value only
 * (the counting digits are aria-hidden).
 */
export function CountUp({ value, decimals = 0, durationMs }: { value: number; decimals?: number; durationMs?: number }) {
  const shown = useCountUp(value, durationMs);
  return (
    <>
      <span className="sr-only">{value.toFixed(decimals)}</span>
      <span aria-hidden>{shown.toFixed(decimals)}</span>
    </>
  );
}
