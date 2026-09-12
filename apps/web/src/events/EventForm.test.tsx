import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import EventForm from "./EventForm";

const category = { id: "cat-1", name: "Running", version: 1 };
const event = { id: "event-1", etag: "\"1\"", title: "Morning run", category_id: "cat-1", category_name: "Running", description: null, mood: "good", location_name: null, latitude: null, longitude: null, occurred_at: "2026-09-09T00:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 };

describe("EventForm", () => {
  it("creates an event before uploading selected images and keeps it after upload failure", async () => {
    const createEvent = vi.fn().mockResolvedValue(event);
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([]);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={createEvent} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} />);
    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.upload(screen.getByLabelText("Images"), new File(["png"], "paw.png", { type: "image/png" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    await waitFor(() => expect(createEvent).toHaveBeenCalledTimes(1));
    expect(uploadEventMedia).toHaveBeenCalledWith("event-1", expect.any(Array));
    expect(await screen.findByText("Pawprint saved")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Image upload failed");
    await user.click(screen.getByRole("button", { name: "Retry image upload" }));
    expect(uploadEventMedia).toHaveBeenCalledTimes(2);
  });

  it("shows a safe API validation failure", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn().mockRejectedValue(new Error("bad request"))} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save Pawprint");
  });

  it("creates a quick category before submitting the complete local event payload", async () => {
    const createCategory = vi.fn().mockResolvedValue({ id: "cat-2", name: "Hiking", version: 1 });
    const createEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createCategory={createCategory} createEvent={createEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText("Title"), "Trail walk");
    await user.type(screen.getByLabelText("New category"), "Hiking");
    await user.click(screen.getByRole("button", { name: "Add category" }));
    await user.clear(screen.getByLabelText("Date and time"));
    await user.type(screen.getByLabelText("Date and time"), "2026-09-09T09:30");
    await user.clear(screen.getByLabelText("Timezone"));
    await user.type(screen.getByLabelText("Timezone"), "Asia/Taipei");
    await user.selectOptions(screen.getByLabelText("Mood"), "good");
    await user.type(screen.getByLabelText("Diary"), "A calm walk");
    await user.type(screen.getByLabelText("Location"), "Elephant Mountain");
    await user.type(screen.getByLabelText("Latitude"), "25.027");
    await user.type(screen.getByLabelText("Longitude"), "121.570");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(createEvent).toHaveBeenCalledTimes(1));
    expect(createCategory).toHaveBeenCalledWith("Hiking");
    expect(createEvent).toHaveBeenCalledWith({
      title: "Trail walk",
      category_id: "cat-2",
      local_datetime: "2026-09-09T09:30",
      timezone: "Asia/Taipei",
      description: "A calm walk",
      mood: "good",
      location_name: "Elephant Mountain",
      latitude: 25.027,
      longitude: 121.57,
    });
  });

  it("updates the selected Pawprint with its latest ETag instead of creating another one", async () => {
    const updateEvent = vi.fn().mockResolvedValue({ ...event, title: "Evening run", etag: "\"2\"", version: 2 });
    const createEvent = vi.fn();
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={event} createEvent={createEvent} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);

    await user.clear(screen.getByLabelText("Title"));
    await user.type(screen.getByLabelText("Title"), "Evening run");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledTimes(1));
    expect(updateEvent).toHaveBeenCalledWith("event-1", expect.objectContaining({ title: "Evening run" }), "\"1\"");
    expect(createEvent).not.toHaveBeenCalled();
  });

  it("wraps selected diary text with the markdown toolbar", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary") as HTMLTextAreaElement;
    await user.type(diary, "quiet morning");
    diary.setSelectionRange(0, 5);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    expect(diary).toHaveValue("**quiet** morning");
  });

  it("does not complete the form until a failed image upload is retried successfully", async () => {
    const onCompleted = vi.fn();
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([]);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn().mockResolvedValue(event)} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} onCompleted={onCompleted} />);
    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.upload(screen.getByLabelText("Images"), new File(["png"], "paw.png", { type: "image/png" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");
    expect(onCompleted).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Retry image upload" }));
    await waitFor(() => expect(onCompleted).toHaveBeenCalledTimes(1));
  });
});
