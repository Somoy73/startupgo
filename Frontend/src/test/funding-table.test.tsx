import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { FundingEvent } from "@/api/backend-types";
import { FundingTable } from "@/components/FundingTable";
import { FundingTotal } from "@/components/FundingTimeline";

const event = (o: Partial<FundingEvent>): FundingEvent => ({
  event_date: null, source_name: "funding_rounds", event_type: "announced_round", round_label: null, amount: null,
  currency: null, price_per_share: null, investor_count: null, source_url: null, status: "verified", confidence: 1,
  details: null, ...o,
});

// Notpla, as GET /api/startups/notpla/rounds returns it (shortened).
const events = [
  event({ event_date: "2017-12-01", source_name: "cordis_projects", event_type: "eu_grant", amount: 50000, currency: "EUR", details: { programme: "H2020 UCUP", role: "coordinator" } }),
  event({ event_date: "2024-04-15", source_name: "uk_sh01", event_type: "priced_round", amount: 16818992.33, currency: "GBP", details: { investors: [] } }),
  event({ event_date: "2024-09", round_label: "series-a", source_url: "https://example.com/notpla-series-a", amount: 20000000, currency: "GBP", details: { lead_investors: "UB Forest Industry Green Growth Fund", notes: "Series A+ (~EUR 23M)." } }),
  event({ event_date: "2026-07-14", source_name: "people_data_labs", event_type: "aggregate", amount: 48219216, currency: "USD", status: "claimed" }),
];

describe("FundingTable", () => {
  it("lists every event but the reported total, newest first, with its type, source and status", () => {
    render(<FundingTable events={events} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(events.length - 1);
    expect(screen.queryByText("Total raised")).not.toBeInTheDocument();
    expect(within(rows[0]!).getByText("Series a")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("Verified")).toHaveClass("tone-success");
    expect(within(rows[0]!).getByRole("link")).toHaveTextContent("Announced");
    expect(within(rows[1]!).getByText("UK Companies House (SH01)")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("EU grant · H2020 UCUP")).toBeInTheDocument();
  });

  it("keeps the curated round's lead investor and notes, and shows amounts in euros", () => {
    render(<FundingTable events={events} />);
    const series = screen.getByText("Series a").closest("tr")!;
    expect(within(series).getByText("Lead: UB Forest Industry Green Growth Fund")).toBeInTheDocument();
    expect(within(series).getByText("Series A+ (~EUR 23M).")).toBeInTheDocument();
    expect(within(series).getByText("€24M")).toBeInTheDocument();
    expect(within(series).getByText("£20M")).toBeInTheDocument();
    expect(screen.getByText("Role: Coordinator")).toBeInTheDocument();
  });

  it("heads the card with the reported total and its source, else the disclosed total", () => {
    const { rerender } = render(<FundingTotal events={events} disclosedUsd={27e6} />);
    expect(screen.getByText("€45M")).toBeInTheDocument();
    expect(screen.getByText("People Data Labs")).toBeInTheDocument();
    expect(screen.getByText("Claimed")).toHaveClass("tone-warning");
    rerender(<FundingTotal events={events.slice(0, 3)} disclosedUsd={27e6} />);
    expect(screen.getByText("Total disclosed ≈ €25M")).toBeInTheDocument();
  });
});
