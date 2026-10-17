import type { FundingEvent } from "../api/backend-types";
import { compactMoney, partialDate } from "../lib/format";
import { eventDetails, eventEur, eventName, FUNDING_KINDS, fundingKind, sourceLabel } from "../lib/funding";
import { Chip, STATUS_TONES } from "./Chip";
import { IconExternal } from "./Icons";

const STATUS_TITLES: Record<string, string> = {
  verified: "From a registry, filing or the funder",
  claimed: "Reported by the company or a data aggregator, not confirmed",
  inferred: "Derived from other facts",
};

/**
 * The same funding events as the timeline, newest first, with their type, source and how sure
 * it is. Scrolls inside a fixed height, header pinned. The same round can appear once per
 * source, e.g. a Series A and the share allotment filed for it.
 */
export function FundingTable({ events }: { events: FundingEvent[] }) {
  // The reported total isn't an event: the card header shows it.
  const rows = events
    .filter((e) => e.event_type !== "aggregate")
    .sort((a, b) => (b.event_date ?? "").localeCompare(a.event_date ?? ""));

  return (
    <div className="table-wrap max-h-96 overflow-y-auto rounded-md border border-border" tabIndex={0} aria-label="Funding events">
      <table className="data [&_th]:sticky [&_th]:top-0 [&_th]:z-10">
        <thead>
          <tr>
            <th>Event</th>
            <th>Date</th>
            <th className="num">Amount</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e, i) => {
            const eur = eventEur(e);
            return (
              <tr key={i}>
                <td>
                  {eventName(e)}
                  <div className="small muted">{FUNDING_KINDS[fundingKind(e)].label}</div>
                  {eventDetails(e).map((d) => (
                    <div key={d} className="small secondary">
                      {d}
                    </div>
                  ))}
                </td>
                <td className="tabular whitespace-nowrap">{partialDate(e.event_date)}</td>
                <td className="num whitespace-nowrap">
                  {compactMoney(Number.isFinite(eur) ? eur : null)}
                  {e.amount != null && e.currency && e.currency.toUpperCase() !== "EUR" && (
                    <div className="small muted">{compactMoney(e.amount, e.currency)}</div>
                  )}
                </td>
                <td className="small">
                  {e.source_url ? (
                    <a
                      href={e.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1"
                    >
                      {sourceLabel(e)}
                      <IconExternal aria-hidden className="size-3 shrink-0" />
                    </a>
                  ) : (
                    <span className="secondary">{sourceLabel(e)}</span>
                  )}
                  <div className="mt-1">
                    <StatusChip event={e} />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Verified, claimed or inferred, coloured; the title says what that means and the confidence. */
export function StatusChip({ event: e }: { event: FundingEvent }) {
  return (
    <Chip
      tone={STATUS_TONES[e.status] ?? "neutral"}
      title={`${STATUS_TITLES[e.status] ?? e.status} · confidence ${Math.round(e.confidence * 100)}%`}
    >
      {e.status.charAt(0).toUpperCase() + e.status.slice(1)}
    </Chip>
  );
}
