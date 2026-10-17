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
import { useChartPalette, withAlpha } from "../lib/chart-theme";
import { StatusChip } from "./FundingTable";
import { compactMoney, toEur } from "../lib/format";
import { eventEur as eur, eventName, FUNDING_KINDS, fundingKind, reportedTotal, sourceLabel, type FundingKind } from "../lib/funding";

ChartJS.register(LinearScale, LogarithmicScale, PointElement, LineElement, Tooltip, Legend);

type Kind = Exclude<FundingKind, "total">;
const PLOTTED: Kind[] = ["equity", "filing", "grant"];

type Point = { x: number; y: number; event: FundingEvent };

/** "2024-09" or "2024-09-15" → 2024.67, so events sit on a plain numeric year axis. */
function decimalYear(date: string): number {
  const [y = 0, m = 1, d = 1] = date.split("-").map(Number);
  return y + (m - 1) / 12 + (d - 1) / 365;
}

/**
 * Every dated funding event with an amount, by type, on a log scale. Not summed: the same
 * round often appears once per source (an announcement and its filing), so a running total
 * would count it twice. The latest reported total, if any, is drawn as a dashed line instead.
 */
export function FundingTimeline({ events }: { events: FundingEvent[] }) {
  const palette = useChartPalette();
  const plotted = events.filter((e) => e.event_date && Number.isFinite(eur(e)) && eur(e) > 0);
  const total = reportedTotal(events);

  if (!plotted.length) return null;
  if (!palette) return <div className="h-56" aria-hidden />;

  const points = (kind: Kind): Point[] =>
    plotted
      .filter((e) => fundingKind(e) === kind)
      .map((e) => ({ x: decimalYear(e.event_date!), y: eur(e), event: e }));
  const years = plotted.map((e) => decimalYear(e.event_date!));
  const [from, to] = [Math.floor(Math.min(...years)), Math.ceil(Math.max(...years) + 0.01)];

  const datasets: ChartDataset<"scatter", Point[]>[] = PLOTTED
    .map((kind) => ({ kind, data: points(kind) }))
    .filter(({ data }) => data.length)
    .map(({ kind, data }) => {
      const color = palette[FUNDING_KINDS[kind].color];
      return {
        label: FUNDING_KINDS[kind].label,
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
            return `${native}${compactMoney(eur(e))} · ${sourceLabel(e)} · ${e.status}`;
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

/**
 * The funding card's headline figure: the total raised a source reports, with its source and
 * status (the dashed line on the timeline), else the backend's total of disclosed rounds.
 */
export function FundingTotal({ events, disclosedUsd }: { events: FundingEvent[] | null; disclosedUsd: number | null }) {
  const total = events ? reportedTotal(events) : undefined;
  if (!total)
    return <span className="small muted">Total disclosed ≈ {compactMoney(toEur(disclosedUsd, "USD"))}</span>;
  return (
    <span className="small muted inline-flex flex-wrap items-center gap-x-1.5 gap-y-1">
      <span>
        Reported total ≈ <strong className="text-foreground">{compactMoney(eur(total))}</strong>
      </span>
      <span aria-hidden>·</span>
      <span>{sourceLabel(total)}</span>
      <StatusChip event={total} />
    </span>
  );
}
