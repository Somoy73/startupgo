import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartDataset,
  type ChartOptions,
} from "chart.js";
import { Scatter } from "react-chartjs-2";
import type { Peer, StartupSummary } from "../api/backend-types";
import { useChartPalette, withAlpha } from "../lib/chart-theme";
import { score } from "../lib/format";
import { Link, useNavigate } from "../lib/navigation";

ChartJS.register(LinearScale, PointElement, Tooltip);

type Point = { x: number; y: number; startup: StartupSummary };

type Props = {
  /** The startup the page is about. */
  slug: string;
  startups: StartupSummary[];
  peers: Peer[];
};

/**
 * Where the startup sits among the others in the database: readiness across, ocean impact up.
 * Its closest peers (by tag overlap) are ringed; click a point to open that startup.
 */
export function PeerScatter({ slug, startups, peers }: Props) {
  const palette = useChartPalette();
  const navigate = useNavigate();
  const peerSlugs = new Set(peers.flatMap((p) => (p.slug ? [p.slug] : [])));
  const point = (s: StartupSummary): Point => ({
    x: s.scores.readiness,
    y: s.scores.ocean_impact,
    startup: s,
  });
  const self = startups.find((s) => s.slug === slug);

  return (
    <section className="card card-pad">
      <div className="card-head">
        <h2>Among its peers</h2>
        <span className="small muted">{startups.length} startups in the database</span>
      </div>
      {!palette || !self ? (
        <div className="aspect-[4/3] w-full" aria-hidden />
      ) : (
        <div className="aspect-[4/3] w-full">
          <Scatter
            role="img"
            aria-label={`${self.name}: readiness ${score(self.scores.readiness)}, ocean impact ${score(self.scores.ocean_impact)}. Closest peers: ${
              peers.map((p) => p.name).join(", ") || "none"
            }.`}
            options={chartOptions(palette.text, palette.grid, (s) => {
              if (s.slug !== slug) navigate(`/startups/${s.slug}`);
            })}
            data={{
              datasets: [
                {
                  label: self.name,
                  data: [point(self)],
                  backgroundColor: palette.primary,
                  borderColor: palette.navy,
                  borderWidth: 2,
                  pointRadius: 9,
                  pointHoverRadius: 11,
                },
                {
                  label: "Closest peers",
                  data: startups.filter((s) => peerSlugs.has(s.slug)).map(point),
                  backgroundColor: withAlpha(palette.ocean, 0.25),
                  borderColor: palette.ocean,
                  borderWidth: 2,
                  pointRadius: 7,
                  pointHoverRadius: 9,
                },
                {
                  label: "Other startups",
                  data: startups.filter((s) => s.slug !== slug && !peerSlugs.has(s.slug)).map(point),
                  backgroundColor: withAlpha(palette.text, 0.35),
                  borderColor: "transparent",
                  pointRadius: 5,
                  pointHoverRadius: 7,
                },
              ] satisfies ChartDataset<"scatter", Point[]>[],
            }}
          />
        </div>
      )}
      {peers.length > 0 && (
        <p className="small muted mt-3">
          Closest peers by shared tags:{" "}
          {peers.map((p, i) => (
            <span key={p.slug ?? p.name}>
              {i > 0 && ", "}
              {p.slug ? <Link to={`/startups/${p.slug}`}>{p.name}</Link> : p.name}
            </span>
          ))}
        </p>
      )}
    </section>
  );
}

function chartOptions(
  text: string,
  grid: string,
  onOpen: (s: StartupSummary) => void,
): ChartOptions<"scatter"> {
  const axis = (title: string) => ({
    min: 0,
    max: 100,
    ticks: { stepSize: 25, color: text },
    grid: { color: grid },
    title: { display: true, text: title, color: text, font: { size: 11, weight: "bold" as const } },
  });
  return {
    responsive: true,
    maintainAspectRatio: false,
    scales: { x: axis("Readiness index"), y: axis("Ocean impact") },
    onHover: (event, elements) => {
      const target = event.native?.target as HTMLElement | undefined;
      if (target) target.style.cursor = elements.length ? "pointer" : "default";
    },
    onClick: (_, elements, chart) => {
      const el = elements[0];
      const raw = el && chart.data.datasets[el.datasetIndex]?.data[el.index];
      if (raw) onOpen((raw as Point).startup);
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => (items[0]?.raw as Point | undefined)?.startup.name ?? "",
          label: (item) => {
            const s = (item.raw as Point).startup;
            return `Readiness ${score(s.scores.readiness)} · Ocean impact ${score(s.scores.ocean_impact)} · Potential ${score(s.scores.potential)}`;
          },
        },
      },
    },
  };
}
