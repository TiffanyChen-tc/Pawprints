import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SearchPage from "./SearchPage";

describe("SearchPage", () => {
  const categories = [{ id: "run", name: "Running", version: 1 }];

  it("applies supported filters together and keeps draft state predictable", async () => {
    const loadSearch = vi.fn().mockResolvedValue([]);
    const user = userEvent.setup();
    render(<SearchPage loadSearch={loadSearch} loadCategories={vi.fn().mockResolvedValue(categories)} />);

    await screen.findByText("No matching Pawprints.");
    await user.type(screen.getByLabelText("Keyword"), "tempo");
    await user.type(screen.getByLabelText("Start date"), "2026-09-01");
    await user.type(screen.getByLabelText("End date"), "2026-09-09");
    await user.selectOptions(screen.getByLabelText("Category"), "run");
    await user.selectOptions(screen.getByLabelText("Mood"), "good");
    await user.type(screen.getByLabelText("Location"), "park");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    expect(loadSearch).toHaveBeenLastCalledWith({
      keyword: "tempo",
      start_date: "2026-09-01",
      end_date: "2026-09-09",
      category_id: "run",
      mood: "good",
      location: "park",
    });
  });

  it("renders search results through the existing event presentation", async () => {
    render(<SearchPage loadSearch={vi.fn().mockResolvedValue([
      { id: "event-1", etag: "\"1\"", title: "Morning run", category_id: "run", category_name: "Running", description: "**good**", mood: "good", location_name: "Park", latitude: null, longitude: null, occurred_at: "2026-09-09T00:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 },
    ])} loadCategories={vi.fn().mockResolvedValue(categories)} />);

    expect(await screen.findByRole("article")).toHaveTextContent("Morning run");
    expect(screen.queryByRole("button", { name: "Edit Morning run" })).toBeNull();
  });

  it("shows a safe empty result state after applying filters", async () => {
    render(<SearchPage loadSearch={vi.fn().mockResolvedValue([])} loadCategories={vi.fn().mockResolvedValue([])} />);

    expect(await screen.findByText("No matching Pawprints.")).toBeInTheDocument();
  });

  it("shows loading and safe API error states", async () => {
    render(<SearchPage loadSearch={vi.fn().mockRejectedValue(new Error("backend detail"))} loadCategories={vi.fn().mockResolvedValue([])} />);

    expect(screen.getByRole("status")).toHaveTextContent("Searching");
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not search your Pawprints");
    expect(screen.getByRole("alert")).not.toHaveTextContent("backend detail");
  });
});
