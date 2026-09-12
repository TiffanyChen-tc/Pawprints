import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import AnalyticsPage, { resolveAnalyticsPreset } from "./AnalyticsPage";

const categories = [{ id: "run", name: "Running", version: 1 }];

describe("AnalyticsPage", () => {
  it("resolves the current-month preset to an explicit inclusive range", () => {
    expect(resolveAnalyticsPreset("current-month", new Date("2026-09-09T10:00:00+08:00"))).toEqual({
      start_date: "2026-09-01",
      end_date: "2026-09-30",
    });
  });

  it("renders backend category counts and requests grouped buckets with explicit dates", async () => {
    const loadCounts = vi.fn()
      .mockResolvedValueOnce({ grouping: "none", start_date: "2026-09-01", end_date: "2026-09-30", items: [{ category_id: "run", category_name: "Running", count: 3 }] })
      .mockResolvedValueOnce({ grouping: "week", start_date: "2026-09-01", end_date: "2026-09-30", buckets: [{ bucket_start_date: "2026-09-07", items: [{ category_id: "run", category_name: "Running", count: 2 }] }] });
    const user = userEvent.setup();

    render(<AnalyticsPage today={new Date("2026-09-09T10:00:00+08:00")} loadCounts={loadCounts} loadCategories={vi.fn().mockResolvedValue(categories)} />);

    expect(await screen.findByText("3")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Grouping"), "week");
    await waitFor(() => expect(loadCounts).toHaveBeenLastCalledWith({ start_date: "2026-09-01", end_date: "2026-09-30", grouping: "week" }));
    expect(await screen.findByText("Week of 2026-09-07")).toBeInTheDocument();
  });

  it("sends category filters and never includes a client-controlled user id", async () => {
    const loadCounts = vi.fn().mockResolvedValue({ grouping: "none", start_date: "2026-09-01", end_date: "2026-09-30", items: [] });
    const user = userEvent.setup();

    render(<AnalyticsPage today={new Date("2026-09-09T10:00:00+08:00")} loadCounts={loadCounts} loadCategories={vi.fn().mockResolvedValue(categories)} />);

    await screen.findByText("No Pawprints in this range.");
    await user.selectOptions(screen.getByLabelText("Category"), "run");

    await waitFor(() => expect(loadCounts).toHaveBeenLastCalledWith({
      start_date: "2026-09-01",
      end_date: "2026-09-30",
      grouping: "none",
      category_id: "run",
    }));
    expect(JSON.stringify(loadCounts.mock.calls)).not.toContain("user_id");
  });

  it("shows loading, empty, and safe API error states", async () => {
    const loadCounts = vi.fn().mockRejectedValue(new Error("private backend detail"));

    render(<AnalyticsPage loadCounts={loadCounts} loadCategories={vi.fn().mockResolvedValue([])} />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading activity summary");
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load your activity summary");
    expect(screen.getByRole("alert")).not.toHaveTextContent("private backend detail");
  });

  it("shows a safe error when category filters cannot load", async () => {
    render(
      <AnalyticsPage
        loadCounts={vi.fn().mockResolvedValue({ grouping: "none", start_date: "2026-09-01", end_date: "2026-09-30", items: [] })}
        loadCategories={vi.fn().mockRejectedValue(new Error("category backend detail"))}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load analytics filters");
    expect(screen.getByRole("alert")).not.toHaveTextContent("category backend detail");
  });
});
