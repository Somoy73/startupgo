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
import { useChartPalette, withAlpha } from "../lib/chart-theme";

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip);

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
  const palette = useChartPalette();

  if (!palette) return <div className="mx-auto aspect-square w-full max-w-80" aria-hidden />;

  const pointColors = labels.map((_, i) => (alerts?.[i] ? palette.alert : palette.ocean));
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
              borderColor: palette.ocean,
              backgroundColor: withAlpha(palette.ocean, 0.2),
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
