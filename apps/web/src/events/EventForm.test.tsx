import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import EventForm from "./EventForm";

const category = { id: "cat-1", name: "Running", version: 1 };
const event = { id: "event-1", etag: "\"1\"", title: "Morning run", category_id: "cat-1", category_name: "Running", description: null, mood: "good", location_name: null, latitude: null, longitude: null, occurred_at: "2026-09-09T00:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 };
const image = (name: string) => new File(["image"], name, { type: "image/jpeg" });

describe("EventForm", () => {
  it("shows a selected image immediately and does not upload it after it is removed", async () => {
    const uploadEventMedia = vi.fn();
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn().mockResolvedValue(event)} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} />);
    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.upload(screen.getByLabelText("Images"), image("A.jpg"));
    expect(await screen.findByRole("img", { name: "A.jpg thumbnail" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove A.jpg" }));
    expect(screen.queryByRole("img", { name: "A.jpg thumbnail" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    await waitFor(() => expect(uploadEventMedia).not.toHaveBeenCalled());
  });

  it("accumulates two file-picker selections, removes one, and uploads only the other", async () => {
    const uploadEventMedia = vi.fn().mockResolvedValue([]);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn().mockResolvedValue(event)} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} />);
    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    const picker = screen.getByLabelText("Images");
    await user.upload(picker, image("A.jpg"));
    await user.upload(picker, image("B.jpg"));
    expect(await screen.findByRole("img", { name: "A.jpg thumbnail" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "B.jpg thumbnail" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove A.jpg" }));
    expect(screen.queryByRole("img", { name: "A.jpg thumbnail" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    await waitFor(() => expect(uploadEventMedia).toHaveBeenCalledWith("event-1", [expect.objectContaining({ name: "B.jpg" })]));
  });

  it("shows saved and pending media together, deletes saved media publicly, and honors the remaining-image limit", async () => {
    const savedMedia = { id: "media-1", display_order: 1, mime_type: "image/jpeg", file_size: 10, created_at: "2026-09-09T00:00:00Z" };
    const deleteMedia = vi.fn().mockResolvedValue(undefined);
    const fetchMediaObjectUrl = vi.fn().mockResolvedValue("blob:existing-private");
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={{ ...event, media: [savedMedia] }} uploadEventMedia={vi.fn()} deleteMedia={deleteMedia} fetchMediaObjectUrl={fetchMediaObjectUrl} onSaved={vi.fn()} />);
    expect(await screen.findByRole("img", { name: "Saved image 1" })).toBeInTheDocument();
    await user.upload(screen.getByLabelText("Images"), image("B.jpg"));
    expect(screen.getByRole("img", { name: "B.jpg thumbnail" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove saved image 1" }));
    await waitFor(() => expect(deleteMedia).toHaveBeenCalledWith("media-1"));
    expect(screen.queryByRole("img", { name: "Saved image 1" })).not.toBeInTheDocument();
  });

  it("loads existing edit media through authenticated blob thumbnails", async () => {
    const savedMedia = { id: "media-1", display_order: 1, mime_type: "image/jpeg", file_size: 10, created_at: "2026-09-09T00:00:00Z" };
    const fetchMediaObjectUrl = vi.fn().mockResolvedValue("blob:existing-private");
    const revokeMediaObjectUrl = vi.fn();

    render(
      <EventForm
        categories={[category]}
        event={{ ...event, media: [savedMedia] }}
        fetchMediaObjectUrl={fetchMediaObjectUrl}
        revokeMediaObjectUrl={revokeMediaObjectUrl}
        uploadEventMedia={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    expect(await screen.findByRole("img", { name: "Saved image 1" })).toHaveAttribute("src", "blob:existing-private");
    expect(fetchMediaObjectUrl).toHaveBeenCalledWith("media-1");
  });

  it("does not upload pending images when a PATCH is stale", async () => {
    const uploadEventMedia = vi.fn();
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={event} updateEvent={vi.fn().mockRejectedValue(Object.assign(new Error("stale"), { status: 412 }))} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} />);
    await user.upload(screen.getByLabelText("Images"), image("A.jpg"));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("changed since you opened it");
    expect(uploadEventMedia).not.toHaveBeenCalled();
  });

  it("allows five total remaining images and rejects selections beyond five", async () => {
    const savedMedia = Array.from({ length: 4 }, (_, index) => ({
      id: `media-${index + 1}`,
      display_order: index + 1,
      mime_type: "image/jpeg",
      file_size: 10,
      created_at: "2026-09-09T00:00:00Z",
    }));
    const user = userEvent.setup();

    render(
      <EventForm
        categories={[category]}
        event={{ ...event, media: savedMedia }}
        fetchMediaObjectUrl={vi.fn().mockImplementation(async (id: string) => `blob:${id}`)}
        uploadEventMedia={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    await user.upload(screen.getByLabelText("Images"), image("allowed.jpg"));
    expect(screen.getByText("5 of 5 images selected.")).toBeInTheDocument();
    await user.upload(screen.getByLabelText("Images"), image("too-many.jpg"));
    expect(screen.getByRole("alert")).toHaveTextContent("Select up to 5 images total.");
    expect(screen.queryByRole("img", { name: "too-many.jpg thumbnail" })).not.toBeInTheDocument();
  });

  it("uploads pending images only after a successful PATCH", async () => {
    const updateEvent = vi.fn().mockResolvedValue({ ...event, title: "Evening run", etag: "\"2\"", version: 2 });
    const uploadEventMedia = vi.fn().mockResolvedValue([]);
    const user = userEvent.setup();

    render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} />);

    await user.upload(screen.getByLabelText("Images"), image("after-patch.jpg"));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(uploadEventMedia).toHaveBeenCalledWith("event-1", [expect.objectContaining({ name: "after-patch.jpg" })]));
    expect(updateEvent.mock.invocationCallOrder[0]).toBeLessThan(uploadEventMedia.mock.invocationCallOrder[0]);
  });
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
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([{ id: "media-1", display_order: 1, mime_type: "image/jpeg", file_size: 10, created_at: "2026-09-09T00:00:00Z" }]);
    const fetchMediaObjectUrl = vi.fn().mockResolvedValue("blob:uploaded-private");
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn().mockResolvedValue(event)} uploadEventMedia={uploadEventMedia} fetchMediaObjectUrl={fetchMediaObjectUrl} onSaved={vi.fn()} onCompleted={onCompleted} />);
    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.upload(screen.getByLabelText("Images"), new File(["png"], "paw.png", { type: "image/png" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");
    expect(onCompleted).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Retry image upload" }));
    await waitFor(() => expect(onCompleted).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("img", { name: "Pawprint image 1" })).toHaveAttribute("src", "blob:uploaded-private");
  });

  it("does not retry an image that the user removed after upload failure", async () => {
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<EventForm categories={[category]} createEvent={vi.fn().mockResolvedValue(event)} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.upload(screen.getByLabelText("Images"), image("A.jpg"));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");

    await user.click(screen.getByRole("button", { name: "Remove A.jpg" }));

    expect(uploadEventMedia).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Retry image upload" })).not.toBeInTheDocument();
  });

  it("does not mutate the saved event again after the last failed image is removed", async () => {
    const createEvent = vi.fn().mockResolvedValue(event);
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed"));
    const onCompleted = vi.fn();
    const user = userEvent.setup();

    render(<EventForm categories={[category]} createEvent={createEvent} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} onCompleted={onCompleted} />);

    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.upload(screen.getByLabelText("Images"), image("A.jpg"));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");

    await user.click(screen.getByRole("button", { name: "Remove A.jpg" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    expect(createEvent).toHaveBeenCalledTimes(1);
    expect(uploadEventMedia).toHaveBeenCalledTimes(1);
    expect(onCompleted).toHaveBeenCalledTimes(1);
  });

  it("updates the saved event after a failed create upload instead of creating a duplicate", async () => {
    const created = { ...event, etag: "\"3\"", version: 3 };
    const updated = { ...created, title: "Evening run", etag: "\"4\"", version: 4 };
    const createEvent = vi.fn().mockResolvedValue(created);
    const updateEvent = vi.fn().mockResolvedValue(updated);
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<EventForm categories={[category]} createEvent={createEvent} updateEvent={updateEvent} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    await user.upload(screen.getByLabelText("Images"), image("A.jpg"));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");

    await user.clear(screen.getByLabelText("Title"));
    await user.type(screen.getByLabelText("Title"), "Evening run");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledTimes(1));
    expect(createEvent).toHaveBeenCalledTimes(1);
    expect(updateEvent).toHaveBeenCalledWith("event-1", expect.objectContaining({ title: "Evening run" }), "\"3\"");
  });

  it("keeps newer pending images visible after retrying an earlier failed upload", async () => {
    const onCompleted = vi.fn();
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<EventForm categories={[category]} createEvent={vi.fn().mockResolvedValue(event)} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} onCompleted={onCompleted} />);

    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    const picker = screen.getByLabelText("Images");
    await user.upload(picker, image("A.jpg"));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");

    await user.upload(picker, image("B.jpg"));
    await user.click(screen.getByRole("button", { name: "Retry image upload" }));

    expect(await screen.findByRole("img", { name: "B.jpg thumbnail" })).toBeInTheDocument();
    expect(onCompleted).not.toHaveBeenCalled();
    expect(uploadEventMedia).toHaveBeenLastCalledWith("event-1", [expect.objectContaining({ name: "A.jpg" })]);
  });

  it("uploads newer pending images against the saved event without creating another event", async () => {
    const onCompleted = vi.fn();
    const createEvent = vi.fn().mockResolvedValue(event);
    const uploadEventMedia = vi.fn().mockRejectedValueOnce(new Error("upload failed")).mockResolvedValue([]);
    const user = userEvent.setup();

    render(<EventForm categories={[category]} createEvent={createEvent} uploadEventMedia={uploadEventMedia} onSaved={vi.fn()} onCompleted={onCompleted} />);

    await user.type(screen.getByLabelText("Title"), "Morning run");
    await user.selectOptions(screen.getByLabelText("Category"), "cat-1");
    const picker = screen.getByLabelText("Images");
    await user.upload(picker, image("A.jpg"));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Image upload failed");

    await user.upload(picker, image("B.jpg"));
    await user.click(screen.getByRole("button", { name: "Retry image upload" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    expect(createEvent).toHaveBeenCalledTimes(1);
    expect(uploadEventMedia).toHaveBeenLastCalledWith("event-1", [expect.objectContaining({ name: "B.jpg" })]);
    await waitFor(() => expect(onCompleted).toHaveBeenCalledTimes(1));
  });
});
