import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TimelinePage from "./TimelinePage";

const entries = [
  { id: "two", etag: "\"1\"", title: "Dinner", category_id: "cat", category_name: "Running", description: null, mood: null, location_name: null, latitude: null, longitude: null, occurred_at: "2026-09-09T10:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 },
  { id: "one", etag: "\"1\"", title: "Morning run", category_id: "cat", category_name: "Running", description: "**good**", mood: "good", location_name: "Park", latitude: null, longitude: null, occurred_at: "2026-09-09T00:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 },
];

describe("TimelinePage", () => {
  it("loads entries chronologically and refetches when the date changes", async () => {
    const loadTimeline = vi.fn().mockResolvedValue(entries);
    const user = userEvent.setup();
    render(<TimelinePage initialDate="2026-09-09" loadTimeline={loadTimeline} loadCategories={vi.fn().mockResolvedValue([])} />);
    expect(await screen.findAllByRole("article")).toHaveLength(2);
    expect(screen.getAllByRole("article").map((entry) => entry.textContent)).toEqual([expect.stringContaining("Morning run"), expect.stringContaining("Dinner")]);
    await user.click(screen.getByRole("button", { name: "Next day" }));
    await waitFor(() => expect(loadTimeline).toHaveBeenLastCalledWith("2026-09-10"));
  });

  it("shows loading, empty, and stale delete review states", async () => {
    const removeEvent = vi.fn().mockRejectedValue(Object.assign(new Error("stale"), { status: 412 }));
    const loadLatest = vi.fn().mockResolvedValue({ ...entries[1], title: "Updated run", etag: "\"2\"", version: 2 });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<TimelinePage initialDate="2026-09-09" loadTimeline={vi.fn().mockResolvedValue(entries.slice(1, 2))} loadCategories={vi.fn().mockResolvedValue([])} removeEvent={removeEvent} loadEvent={loadLatest} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    await screen.findByText("Morning run");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Morning run/ }));
    await user.click(screen.getByRole("button", { name: "Delete Morning run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("changed since you loaded it");
    expect(screen.getByText("Updated run")).toBeInTheDocument();
  });

  it("reloads the latest event into the form after a stale edit conflict", async () => {
    const staleEvent = { ...entries[1], title: "Morning run", etag: "\"1\"", version: 1 };
    const latestEvent = { ...staleEvent, title: "Updated run", etag: "\"2\"", version: 2 };
    const updateEvent = vi.fn().mockRejectedValue(Object.assign(new Error("stale"), { status: 412 }));
    const loadLatest = vi.fn().mockResolvedValue(latestEvent);
    const user = userEvent.setup();

    render(
      <TimelinePage
        initialDate="2026-09-09"
        loadTimeline={vi.fn().mockResolvedValue([staleEvent])}
        loadCategories={vi.fn().mockResolvedValue([{ id: "cat", name: "Running", version: 1 }])}
        loadEvent={loadLatest}
        updateEvent={updateEvent}
      />,
    );

    await screen.findByText("Morning run");
    await user.click(screen.getByRole("button", { name: /Morning run/ }));
    await user.click(screen.getByRole("button", { name: "Edit Morning run" }));
    await user.clear(screen.getByLabelText("Title"));
    await user.type(screen.getByLabelText("Title"), "My edit");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("changed since you loaded it");
    expect(screen.getByLabelText("Title")).toHaveValue("Updated run");
    await waitFor(() => expect(loadLatest).toHaveBeenCalledWith("one"));
  });

  it("returns to the browser local date from another day", async () => {
    const user = userEvent.setup();
    render(<TimelinePage initialDate="2026-09-08" today="2026-09-09" loadTimeline={vi.fn().mockResolvedValue([])} loadCategories={vi.fn().mockResolvedValue([])} />);
    await screen.findByText("No Pawprints for this date yet.");
    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(screen.getByLabelText("Timeline date")).toHaveValue("2026-09-09");
  });
});
