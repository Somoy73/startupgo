import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SearchProgress } from "@/components/SearchProgress";

describe("SearchProgress", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("walks through the search steps as time passes", () => {
    render(<SearchProgress steps />);
    expect(screen.getByRole("status")).toHaveTextContent("Understanding your query…");
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByRole("status")).toHaveTextContent("Searching the knowledge graph…");
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.getByRole("status")).toHaveTextContent("Ranking matches…");
    act(() => { vi.advanceTimersByTime(10000); });
    expect(screen.getByRole("status")).toHaveTextContent("Still working");
  });

  it("shows a fixed label without steps", () => {
    render(<SearchProgress label="Loading startups…" />);
    act(() => { vi.advanceTimersByTime(10000); });
    expect(screen.getByRole("status")).toHaveTextContent("Loading startups…");
  });
});
