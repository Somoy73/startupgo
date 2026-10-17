import type { ReactNode } from "react";
import { KTH_DIMENSIONS, type StartupSummary } from "../../api/backend-types";
import { compactMoney, partialDate, PIPELINE_LABELS, stageLabel, toEur } from "../../lib/format";
import { Link } from "@tanstack/react-router";
import type { SearchSortKey } from "../../lib/discover-search";
import { BandBadge, LevelPill, Meter } from "../Scores";

export type Column = {
  id: string;
  header: string;
  /** Clicking the header sorts by this; no key, no sorting. */
  sortKey?: SearchSortKey;
  /** Centred, tabular numbers. */
  numeric?: boolean;
  /** Always shown; not offered in the column picker. */
  locked?: boolean;
  defaultVisible: boolean;
  cellClassName?: string;
  cell: (s: StartupSummary) => ReactNode;
};

/** Placeholder for a startup the research agent hasn't scored yet. */
const PENDING = <span className="muted" title="Not assessed yet: open it to run research">—</span>;

const levelColumns: Column[] = KTH_DIMENSIONS.map((d) => ({
  id: d.key,
  header: d.code,
  sortKey: d.key,
  numeric: true,
  defaultVisible: d.key === "trl" || d.key === "brl",
  cell: (s) => !s.assessed ? PENDING : <LevelPill level={s.readiness[d.key]} label={d.code} />,
}));

export const COLUMNS: Column[] = [
  {
    id: "name",
    header: "Startup",
    sortKey: "name",
    locked: true,
    defaultVisible: true,
    cellClassName: "name-cell",
    cell: (s) => (
      <>
        <Link to="/startups/$slug" params={{ slug: s.slug }} onClick={(e) => e.stopPropagation()}>
          <strong>{s.name}</strong>
        </Link>
        <span>{s.tagline}</span>
      </>
    ),
  },
  {
    id: "sector",
    header: "Sector · Country",
    defaultVisible: true,
    cellClassName: "secondary small",
    cell: (s) => `${s.sector} · ${s.country}`,
  },
  {
    id: "stage",
    header: "Stage",
    sortKey: "stage",
    defaultVisible: false,
    cell: (s) => stageLabel(s.stage),
  },
  ...levelColumns,
  {
    id: "readiness",
    header: "Readiness",
    sortKey: "readiness",
    defaultVisible: false,
    cell: (s) => !s.assessed ? PENDING : <Meter value={s.scores.readiness} label="Readiness index" />,
  },
  {
    id: "ocean",
    header: "Ocean impact",
    sortKey: "ocean",
    defaultVisible: true,
    cell: (s) =>
      !s.assessed ? PENDING : s.scores.ocean_evidence_known === false ? (
        <span className="muted" title="No ocean impact evidence on record">No evidence</span>
      ) : (
        <Meter value={s.scores.ocean_impact} label="Ocean impact" />
      ),
  },
  {
    id: "momentum",
    header: "Momentum",
    sortKey: "momentum",
    defaultVisible: false,
    cell: (s) => !s.assessed ? PENDING : <Meter value={s.scores.momentum} label="Funding momentum" />,
  },
  {
    id: "potential",
    header: "Investment potential",
    sortKey: "potential",
    defaultVisible: true,
    cell: (s) => !s.assessed ? PENDING : (
      <div className="row-gap">
        <Meter value={s.scores.potential} label="Investment potential" />
        <BandBadge band={s.scores.band} />
      </div>
    ),
  },
  {
    id: "funding",
    header: "Disclosed funding",
    sortKey: "funding",
    numeric: true,
    defaultVisible: false,
    cell: (s) => compactMoney(toEur(s.total_disclosed_usd || null, "USD")),
  },
  {
    id: "lastRound",
    header: "Last round",
    sortKey: "lastRound",
    defaultVisible: false,
    cell: (s) => partialDate(s.last_round_on),
  },
  {
    id: "pipeline",
    header: "Pipeline",
    sortKey: "pipeline",
    defaultVisible: true,
    cell: (s) => <span className="chip">{PIPELINE_LABELS[s.pipeline_stage]}</span>,
  },
];

export const DEFAULT_COLUMNS = COLUMNS.filter((c) => c.defaultVisible).map((c) => c.id);
