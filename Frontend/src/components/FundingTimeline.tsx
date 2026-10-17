import {
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  LogarithmicScale,
  PointElement,
  Tooltip,
  type ChartDataset,
  type ChartOptions,
} from "chart.js";
import { Scatter } from "react-chartjs-2";
import type { FundingEvent } from "../api/backend-types";
import { useChartPalette, withAlpha, type ChartPalette } from "../lib/chart-theme";
import { compactMoney, stageLabel, toEur } from "../lib/format";

ChartJS.register(LinearScale, LogarithmicScale, PointElement, LineElement, Tooltip, Legend);

const KINDS = {
  equity: { label: "Equity round", types: ["announced_round", "priced_round"], color: "primary" },
  filing: { label: "SEC filing", types: ["form_d"], color: "navy" },
  grant: { label: "Grant", types: ["eu_grant", "grant"], color: "success" },
} as const satisfies Record<string, { label: string; types: string[]; color: keyof ChartPalette }>;
type Kind = keyof typeof KINDS;

type Point = { x: number; y: number; event: FundingEvent };

/** "2024-09" or "2024-09-15" → 2024.67, so events sit on a plain numeric year axis. */
function decimalYear(date: string): number {
  const [y = 0, m = 1, d = 1] = date.split("-").map(Number);
  return y + (m - 1) / 12 + (d - 1) / 365;
}

/** The event's amount in euros, or NaN when it has none (or an unknown currency). */
const eur = (e: FundingEvent) => toEur(e.amount, e.currency) ?? NaN;

const eventName = (e: FundingEvent) =>
  e.round_label
    ? stageLabel(e.round_label)
    : e.event_type === "priced_round"
      ? "Priced share allotment"
      : e.event_type === "form_d"
        ? "Form D filing"
        : stageLabel(e.event_type.replace("_", " "));

/**
 * Every dated funding event with an amount, by type, on a log scale. Not summed: the same
 * round often appears once per source (an announcement and its filing), so a running total
 * would count it twice. The latest reported total, if any, is drawn as a dashed line instead.
 */
export function FundingTimeline({ events }: { events: FundingEvent[] }) {
  const palette = useChartPalette();
  const plotted = events.filter((e) => e.event_date && Number.isFinite(eur(e)) && eur(e) > 0);
  const total = events.filter((e) => e.event_type === "aggregate" && Number.isFinite(eur(e))).at(-1);

  if (!plotted.length) return null;
  if (!palette) return <div className="h-56" aria-hidden />;

  const points = (kind: Kind): Point[] =>
    plotted
      .filter((e) => (KINDS[kind].types as readonly string[]).includes(e.event_type))
      .map((e) => ({ x: decimalYear(e.event_date!), y: eur(e), event: e }));
  const years = plotted.map((e) => decimalYear(e.event_date!));
  const [from, to] = [Math.floor(Math.min(...years)), Math.ceil(Math.max(...years) + 0.01)];

  const datasets: ChartDataset<"scatter", Point[]>[] = (Object.keys(KINDS) as Kind[])
    .map((kind) => ({ kind, data: points(kind) }))
    .filter(({ data }) => data.length)
    .map(({ kind, data }) => {
      const color = palette[KINDS[kind].color];
      return {
        label: KINDS[kind].label,
        data,
        backgroundColor: data.map((p) => (p.event.status === "verified" ? color : "transparent")),
        borderColor: color,
        borderWidth: 2,
        pointRadius: 6,
        pointHoverRadius: 8,
      };
    });
  if (total) {
    const y = eur(total);
    datasets.push({
      label: "Reported total raised",
      data: [
        { x: from, y, event: total },
        { x: to, y, event: total },
      ],
      showLine: true,
      borderColor: withAlpha(palette.text, 0.7),
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 0,
    });
  }

  const options: ChartOptions<"scatter"> = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        type: "linear",
        min: from,
        max: to,
        ticks: { stepSize: 1, color: palette.text, callback: (v) => String(v) },
        grid: { color: palette.grid },
      },
      y: {
        type: "logarithmic",
        ticks: {
          color: palette.text,
          // Only round powers of ten and their halves, e.g. $1M, $5M, $10M.
          callback: (v) => {
            const n = Number(v);
            const lead = n / 10 ** Math.floor(Math.log10(n));
            return lead === 1 || lead === 5 ? compactMoney(n) : null;
          },
        },
        grid: { color: palette.grid },
      },
    },
    plugins: {
      legend: {
        position: "bottom",
        // padding: space around each item, so the legend entries don't run together.
        labels: { color: palette.text, usePointStyle: true, boxWidth: 8, padding: 20, font: { size: 11 } },
      },
      tooltip: {
        callbacks: {
          title: (items) => {
            const e = (items[0]?.raw as Point | undefined)?.event;
            return e ? `${eventName(e)} · ${e.event_date}` : "";
          },
          label: (item) => {
            const e = (item.raw as Point).event;
            const native =
              e.currency && e.currency.toUpperCase() !== "EUR"
                ? `${compactMoney(e.amount, e.currency)} ≈ `
                : "";
            return `${native}${compactMoney(eur(e))} · ${e.source_name.replaceAll("_", " ")} · ${e.status}`;
          },
        },
      },
    },
  };

  return (
    <figure className="mb-4">
      <div className="h-56">
        <Scatter
          role="img"
          aria-label={`Funding timeline: ${plotted
            .map((e) => `${eventName(e)} ${e.event_date} ${compactMoney(eur(e))}`)
            .join("; ")}`}
          options={options}
          data={{ datasets }}
        />
      </div>
      <figcaption className="small muted mt-1">
        In euros at approximate rates, log scale. Hollow points are claimed, not verified. The same
        round can appear once per source.
      </figcaption>
    </figure>
  );
}
