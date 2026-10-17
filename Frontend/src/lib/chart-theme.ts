import { useEffect, useState } from "react";

/** Theme colours as real values: a canvas can't read CSS variables. */
export type ChartPalette = {
  ocean: string;
  primary: string;
  navy: string;
  success: string;
  amber: string;
  alert: string;
  grid: string;
  text: string;
};

function readPalette(): ChartPalette {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    ocean: v("--ocean", "#2a78d6"),
    primary: v("--primary", "#2459c7"),
    navy: v("--navy", "#13254a"),
    success: v("--success", "#2c9a62"),
    amber: "oklch(0.666 0.179 58.318)", // Tailwind amber-600, as in the band colours
    alert: v("--destructive", "#d03b3b"),
    grid: v("--border", "#e1e0d9"),
    text: v("--muted-foreground", "#898781"),
  };
}

/**
 * The palette, read once in the browser. Null during server rendering and the first client
 * render, so charts can show a same-sized placeholder until it's there.
 */
export function useChartPalette(): ChartPalette | null {
  const [palette, setPalette] = useState<ChartPalette | null>(null);
  useEffect(() => setPalette(readPalette()), []);
  return palette;
}

/** `oklch(0.6 0.17 248)` → `oklch(0.6 0.17 248 / 0.2)`; other formats are returned as they are. */
export function withAlpha(color: string, alpha: number): string {
  return /^oklch\([^/]*\)$/.test(color) ? color.replace(/\)$/, ` / ${alpha})`) : color;
}
