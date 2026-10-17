import { ArcElement, Chart as ChartJS, RadialLinearScale, Tooltip, type ChartOptions } from "chart.js";
import { PolarArea } from "react-chartjs-2";
import type { OceanImpactArea, OceanKpiEvidence } from "../api/backend-types";
import { useChartPalette, withAlpha } from "../lib/chart-theme";
import { cn } from "../lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";

ChartJS.register(ArcElement, RadialLinearScale, Tooltip);

const EVIDENCE = ["None", "Claimed", "Evidenced", "Measured", "Verified"];

/**
 * One wedge per Ocean Impact Navigator area (A-F), as long as the strongest evidence for any
 * of its KPIs (0-4). Empty wedges show which areas the startup has no evidence for.
 */
export function OceanAreaChart({ areas, kpis }: { areas: OceanImpactArea[]; kpis: OceanKpiEvidence[] }) {
  const palette = useChartPalette();
  if (!areas.length) return null;
  if (!palette) return <div className="mx-auto aspect-square w-full max-w-72" aria-hidden />;

  const best = areas.map((a) =>
    Math.max(0, ...kpis.filter((k) => k.area_code === a.code).map((k) => k.evidence_level)),
  );
  const count = (code: string) => kpis.filter((k) => k.area_code === code && k.evidence_level > 0).length;

  const options: ChartOptions<"polarArea"> = {
    responsive: true,
    maintainAspectRatio: true,
    scales: {
      r: {
        min: 0,
        max: 4,
        ticks: { stepSize: 1, display: false },
        grid: { color: palette.grid },
        angleLines: { display: true, color: palette.grid },
        pointLabels: {
          display: true,
          centerPointLabels: true,
          color: palette.text,
          font: { size: 12, weight: "bold" },
        },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => {
            const a = areas[items[0]?.dataIndex ?? 0];
            return a ? `${a.code} · ${a.name}` : "";
          },
          label: (item) => {
            const a = areas[item.dataIndex];
            const n = a ? count(a.code) : 0;
            return `Best evidence: ${EVIDENCE[item.raw as number] ?? "None"} · ${n} KPI${n === 1 ? "" : "s"}`;
          },
        },
      },
    },
  };

  return (
    <figure className="mb-4">
      <div className="mx-auto w-full max-w-72">
        <PolarArea
          role="img"
          aria-label={`Strongest ocean impact evidence by area: ${areas
            .map((a, i) => `${a.code} ${a.name} ${EVIDENCE[best[i] ?? 0]}`)
            .join(", ")}`}
          options={options}
          data={{
            labels: areas.map((a) => a.code),
            datasets: [
              {
                data: best,
                backgroundColor: best.map((b) => withAlpha(palette.success, 0.2 + 0.15 * b)),
                borderColor: palette.success,
                borderWidth: 1.5,
              },
            ],
          }}
        />
      </div>
      <ul className="mt-2 flex flex-wrap justify-center gap-1.5" aria-label="Ocean impact areas">
        {areas.map((a, i) => (
          <li key={a.code}>
            <AreaHint area={a} best={best[i] ?? 0} kpis={kpis.filter((k) => k.area_code === a.code && k.evidence_level > 0)} />
          </li>
        ))}
      </ul>
      <figcaption className="small muted mt-2 text-center">
        Strongest evidence per area: 1 claimed · 2 evidenced · 3 measured · 4 verified
      </figcaption>
    </figure>
  );
}

/** One area's letter as a button; the hint names the area and lists the KPIs it has evidence for. */
export function AreaHint({ area, best, kpis }: { area: OceanImpactArea; best: number; kpis: OceanKpiEvidence[] }) {
  return (
    <Popover>
      <PopoverTrigger
        aria-label={`${area.code}: ${area.name}, ${EVIDENCE[best]}`}
        className={cn(
          "inline-flex size-7 items-center justify-center rounded-full border text-xs font-bold focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          best > 0
            ? "border-success bg-success/15 text-success hover:bg-success/25"
            : "border-border text-muted-foreground hover:text-foreground",
        )}
      >
        {area.code}
      </PopoverTrigger>
      <PopoverContent align="center" className="w-72 text-sm">
        <p className="font-bold">
          {area.code} · {area.name}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">Strongest evidence: {EVIDENCE[best]}</p>
        {kpis.length > 0 ? (
          <ul className="mt-2 space-y-1.5">
            {kpis.map((k) => (
              <li key={k.kpi_code}>
                <strong>{k.kpi_code}</strong> {k.kpi_name}
                <span className="text-muted-foreground"> · {k.evidence_label}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-muted-foreground">No evidence recorded for this area.</p>
        )}
      </PopoverContent>
    </Popover>
  );
}
