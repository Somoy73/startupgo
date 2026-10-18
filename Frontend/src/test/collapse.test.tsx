import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Collapse } from "@/components/Collapse";

describe("Collapse", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("shows its content at once when opened, and hides it after the slide when closed", () => {
    const { rerender } = render(<Collapse open={false} id="c">Details</Collapse>);
    expect(screen.getByText("Details")).not.toBeVisible();

    rerender(<Collapse open id="c">Details</Collapse>);
    expect(screen.getByText("Details")).toBeVisible();
    act(() => { vi.advanceTimersByTime(20); }); // the next frame expands it
    expect(document.getElementById("c")).toHaveAttribute("data-open", "true");

    rerender(<Collapse open={false} id="c">Details</Collapse>);
    expect(document.getElementById("c")).toHaveAttribute("data-open", "false");
    expect(screen.getByText("Details")).toBeVisible(); // still sliding shut
    act(() => { vi.advanceTimersByTime(250); });
    expect(screen.getByText("Details")).not.toBeVisible();
  });
});
