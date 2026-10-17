import { useEffect, useState } from "react";
import {
  Chart as ChartJS,
  Filler,
  LineElement,
  PointElement,
  RadialLinearScale,
  Tooltip,
  type ChartOptions,
} from "chart.js";
import { Radar } from "react-chartjs-2";

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip);

type Palette = { line: string; fill: string; alert: string; grid: string; text: string };

/** Theme colours from the CSS variables (the canvas needs real colour values). */
function readPalette(): Palette {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  const line = v("--ocean", "#2a78d6");
  return {
    line,
    fill: withAlpha(line, 0.2),
    alert: v("--destructive", "#d03b3b"),
    grid: v("--border", "#e1e0d9"),
    text: v("--muted-foreground", "#898781"),
  };
}

/** `oklch(0.6 0.17 248)` → `oklch(0.6 0.17 248 / 0.2)`; other formats are returned as they are. */
function withAlpha(color: string, alpha: number): string {
  return /^oklch\([^/]*\)$/.test(color) ? color.replace(/\)$/, ` / ${alpha})`) : color;
}

type Props = {
  /** One axis per label. */
  labels: string[];
  values: number[];
  max: number;
  /** Distance between the scale's rings. */
  step: number;
  /** Read out instead of the canvas, e.g. "TRL 7, BRL 5, …". */
  ariaLabel: string;
  /** Axes to mark in the alert colour, e.g. lagging dimensions. */
  alerts?: boolean[];
  /** Tooltip lines for one axis. */
  tooltip?: (index: number) => { title: string; label: string };
};

/**
 * A single-series radar in the theme's colours. Rendered in the browser only: the server
 * can't draw a canvas, so it gets a same-sized placeholder.
 */
export function RadarChart({ labels, values, max, step, ariaLabel, alerts, tooltip }: Props) {
  const [palette, setPalette] = useState<Palette | null>(null);
  useEffect(() => setPalette(readPalette()), []);

  if (!palette) return <div className="mx-auto aspect-square w-full max-w-80" aria-hidden />;

  const pointColors = labels.map((_, i) => (alerts?.[i] ? palette.alert : palette.line));
  const options: ChartOptions<"radar"> = {
    responsive: true,
    maintainAspectRatio: true,
    scales: {
      r: {
        min: 0,
        max,
        ticks: {
          stepSize: step,
          color: palette.text,
          backdropColor: "transparent",
          font: { size: 10 },
        },
        grid: { color: palette.grid },
        angleLines: { color: palette.grid },
        pointLabels: { color: palette.text, font: { size: 12, weight: "bold" } },
      },
    },
    plugins: {
      legend: { display: false },
      ...(tooltip && {
        tooltip: {
          callbacks: {
            title: (items) => tooltip(items[0]?.dataIndex ?? 0).title,
            label: (item) => tooltip(item.dataIndex).label,
          },
        },
      }),
    },
  };

  return (
    <div className="mx-auto w-full max-w-80">
      <Radar
        role="img"
        aria-label={ariaLabel}
        options={options}
        data={{
          labels,
          datasets: [
            {
              data: values,
              borderColor: palette.line,
              backgroundColor: palette.fill,
              borderWidth: 2,
              fill: true,
              pointBackgroundColor: pointColors,
              pointBorderColor: pointColors,
              pointHoverBackgroundColor: pointColors,
              pointHoverBorderColor: pointColors,
              pointRadius: 4,
              pointHoverRadius: 6,
            },
          ],
        }}
      />
    </div>
  );
}
