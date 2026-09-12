import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TimelinePage from "./TimelinePage";

const entries = [
  { id: "two", etag: "\"1\"", title: "Dinner", category_id: "cat", category_name: "Running", description: null, mood: null, location_name: null, latitude: null, longitude: null, occurred_at: "2026-09-09T10:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 },
  { id: "one", etag: "\"1\"", title: "Morning run", category_id: "cat", category_name: "Running", description: "**good**", mood: "good", location_name: "Park", latitude: null, longitude: null, occurred_at: "2026-09-09T00:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 },
];

describe("TimelinePage", () => {
  it("does not let a late timeline response overwrite the currently selected date", async () => {
    let resolveFirst: ((events: typeof entries) => void) | undefined;
    const loadTimeline = vi.fn()
      .mockImplementationOnce(() => new Promise<typeof entries>((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce([{ ...entries[1], id: "current", title: "Current day", local_date: "2026-09-10" }]);
    const user = userEvent.setup();

    render(<TimelinePage initialDate="2026-09-09" loadTimeline={loadTimeline} loadCategories={vi.fn().mockResolvedValue([])} />);

    await user.click(screen.getByRole("button", { name: "Next day" }));
    expect(await screen.findByText("Current day")).toBeInTheDocument();

    resolveFirst?.([{ ...entries[1], id: "late", title: "Late previous day", local_date: "2026-09-09" }]);

    await waitFor(() => expect(loadTimeline).toHaveBeenCalledWith("2026-09-10"));
    expect(screen.queryByText("Late previous day")).not.toBeInTheDocument();
    expect(screen.getByText("Current day")).toBeInTheDocument();
  });

  it("refetches the selected date after a cross-date create and only renders the event on its own date", async () => {
    const crossDate = { ...entries[1], id: "cross", title: "Previous day run", local_date: "2026-09-11" };
    const loadTimeline = vi.fn().mockImplementation(async (date: string) => date === "2026-09-11" ? [crossDate] : []);
    const user = userEvent.setup();
    render(<TimelinePage initialDate="2026-09-12" loadTimeline={loadTimeline} loadCategories={vi.fn().mockResolvedValue([{ id: "cat", name: "Running", version: 1 }])} createEvent={vi.fn().mockResolvedValue(crossDate)} />);
    await screen.findByText("No Pawprints for this date yet.");
    await user.click(screen.getByRole("button", { name: "New Pawprint" }));
    await user.type(screen.getByLabelText("Title"), "Previous day run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat");
    await user.clear(screen.getByLabelText("Date and time"));
    await user.type(screen.getByLabelText("Date and time"), "2026-09-11T09:00");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(screen.queryByText("Previous day run")).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Timeline date"));
    await user.type(screen.getByLabelText("Timeline date"), "2026-09-11");
    expect(await screen.findByText("Previous day run")).toBeInTheDocument();
  });

  it("keeps the form open when a post-save image upload fails so the image can be retried", async () => {
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([]);
    const user = userEvent.setup();

    render(
      <TimelinePage
        initialDate="2026-09-12"
        loadTimeline={vi.fn().mockResolvedValue([])}
        loadCategories={vi.fn().mockResolvedValue([{ id: "cat", name: "Running", version: 1 }])}
        createEvent={vi.fn().mockResolvedValue({ ...entries[1], id: "created", title: "Image day", local_date: "2026-09-12" })}
        uploadEventMedia={uploadEventMedia}
      />,
    );

    await screen.findByText("No Pawprints for this date yet.");
    await user.click(screen.getByRole("button", { name: "New Pawprint" }));
    await user.type(screen.getByLabelText("Title"), "Image day");
    await user.selectOptions(screen.getByLabelText("Category"), "cat");
    await user.upload(screen.getByLabelText("Images"), new File(["image"], "retry.jpg", { type: "image/jpeg" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");
    expect(screen.getByRole("button", { name: "Retry image upload" })).toBeInTheDocument();
  });

  it("refetches backend truth after an edit moves an event and after deletion", async () => {
    const loadTimeline = vi.fn().mockResolvedValueOnce([entries[1]]).mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<TimelinePage initialDate="2026-09-09" loadTimeline={loadTimeline} loadCategories={vi.fn().mockResolvedValue([{ id: "cat", name: "Running", version: 1 }])} loadMedia={vi.fn().mockResolvedValue([])} updateEvent={vi.fn().mockResolvedValue({ ...entries[1], local_date: "2026-09-10" })} removeEvent={vi.fn().mockResolvedValue(undefined)} />);
    await screen.findByText("Morning run");
    await user.click(screen.getByRole("button", { name: /Morning run/ }));
    await user.click(screen.getByRole("button", { name: "Edit Morning run" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    await waitFor(() => expect(screen.queryByText("Morning run")).not.toBeInTheDocument());
  });

  it("refetches backend truth after deleting an event", async () => {
    const loadTimeline = vi.fn().mockResolvedValueOnce([entries[1]]).mockResolvedValueOnce([]);
    const removeEvent = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <TimelinePage
        initialDate="2026-09-09"
        loadTimeline={loadTimeline}
        loadCategories={vi.fn().mockResolvedValue([{ id: "cat", name: "Running", version: 1 }])}
        loadMedia={vi.fn().mockResolvedValue([])}
        removeEvent={removeEvent}
      />,
    );

    await screen.findByText("Morning run");
    await user.click(screen.getByRole("button", { name: /Morning run/ }));
    await user.click(screen.getByRole("button", { name: "Delete Morning run" }));

    await waitFor(() => expect(screen.queryByText("Morning run")).not.toBeInTheDocument());
    expect(removeEvent).toHaveBeenCalledWith("one", "\"1\"");
  });
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
    render(<TimelinePage initialDate="2026-09-09" loadTimeline={vi.fn().mockResolvedValue(entries.slice(1, 2))} loadCategories={vi.fn().mockResolvedValue([])} removeEvent={removeEvent} loadEvent={loadLatest} loadMedia={vi.fn().mockResolvedValue([])} />);
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
        loadMedia={vi.fn().mockResolvedValue([])}
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
