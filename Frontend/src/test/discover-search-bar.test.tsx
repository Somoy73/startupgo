import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DiscoverSearchBar } from "@/components/DiscoverSearchBar";
import { emptyFilters } from "@/lib/discover-search";

const base = { filters: emptyFilters(), busy: false, onSearch: () => {}, onFiltersChange: () => {}, onClear: () => {} };

describe("Search screen EU Projects switch", () => {
  it("starts off and asks for EU projects when pressed", () => {
    const onTypeChange = vi.fn();
    render(<DiscoverSearchBar query="" type="startups" {...base} onTypeChange={onTypeChange} />);
    const toggle = screen.getByRole("button", { name: "EU Projects" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(onTypeChange).toHaveBeenCalledWith("eu-projects");
  });

  it("reads as on, hides the startup filters, and turns back off when pressed", () => {
    const onTypeChange = vi.fn();
    render(<DiscoverSearchBar query="seaweed" type="eu-projects" {...base} onTypeChange={onTypeChange} />);
    const toggle = screen.getByRole("button", { name: "EU Projects" });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "Filters" })).not.toBeInTheDocument();
    expect(screen.queryByText("Matches for “seaweed”")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(onTypeChange).toHaveBeenCalledWith("startups");
  });

  it("no longer offers the old startups / EU projects dropdown", () => {
    render(<DiscoverSearchBar query="" type="startups" {...base} onTypeChange={vi.fn()} />);
    expect(screen.queryByLabelText("What to search")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
