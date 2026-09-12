import { createEvent, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import EventForm from "./EventForm";
import MarkdownDescription from "./MarkdownDescription";

const category = { id: "cat-1", name: "Running", version: 1 };
const event = { id: "event-1", etag: "\"1\"", title: "Morning run", category_id: "cat-1", category_name: "Running", description: null, mood: "good", location_name: null, latitude: null, longitude: null, occurred_at: "2026-09-09T00:00:00Z", timezone: "Asia/Taipei", local_date: "2026-09-09", version: 1 };
const image = (name: string) => new File(["image"], name, { type: "image/jpeg" });

function selectContents(element: Element) {
  const range = document.createRange();
  range.selectNodeContents(element);
  window.getSelection()?.removeAllRanges();
  window.getSelection()?.addRange(range);
}

function selectText(node: Node, start: number, end: number) {
  const range = document.createRange();
  range.setStart(node, start);
  range.setEnd(node, end);
  window.getSelection()?.removeAllRanges();
  window.getSelection()?.addRange(range);
}

function textNodeContaining(root: Node, text: string) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if ((node.textContent ?? "").includes(text)) return node;
    node = walker.nextNode();
  }
  throw new Error(`Could not find text node containing ${text}`);
}

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

  it("keeps saved-media removal local until Save, then deletes through the public API", async () => {
    const savedMedia = { id: "media-1", display_order: 1, mime_type: "image/jpeg", file_size: 10, created_at: "2026-09-09T00:00:00Z" };
    const deleteMedia = vi.fn().mockResolvedValue(undefined);
    const fetchMediaObjectUrl = vi.fn().mockResolvedValue("blob:existing-private");
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={{ ...event, media: [savedMedia] }} updateEvent={vi.fn().mockResolvedValue(event)} uploadEventMedia={vi.fn().mockResolvedValue([])} deleteMedia={deleteMedia} fetchMediaObjectUrl={fetchMediaObjectUrl} onSaved={vi.fn()} />);
    expect(await screen.findByRole("img", { name: "Saved image 1" })).toBeInTheDocument();
    await user.upload(screen.getByLabelText("Images"), image("B.jpg"));
    expect(screen.getByRole("img", { name: "B.jpg thumbnail" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove saved image 1" }));
    expect(deleteMedia).not.toHaveBeenCalled();
    expect(screen.queryByRole("img", { name: "Saved image 1" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    await waitFor(() => expect(deleteMedia).toHaveBeenCalledWith("media-1"));
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

  it("opens approved diary Markdown as visual formatting instead of raw markers", () => {
    render(<EventForm categories={[category]} event={{ ...event, description: "**bold** and *italic* and ~~struck~~" }} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    expect(diary.querySelector("strong")?.textContent).toBe("bold");
    expect(diary.querySelector("em")?.textContent).toBe("italic");
    expect(diary.querySelector("del")?.textContent).toBe("struck");
  });

  it("formats a diary selection visually with the toolbar", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "quiet morning");
    const range = document.createRange();
    range.setStart(diary.firstChild!, 0);
    range.setEnd(diary.firstChild!, 5);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    expect(diary.querySelector("strong")?.textContent).toBe("quiet");
  });

  it("toggles bold formatting off without changing the selected text", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "quiet morning");

    selectText(diary.firstChild!, 0, 5);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    expect(diary.querySelector("strong")?.textContent).toBe("quiet");

    selectContents(diary.querySelector("strong")!);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    expect(diary.querySelector("strong")).toBeNull();
    expect(diary.textContent).toBe("quiet morning");
  });

  it("toggles italic and strikethrough formatting off", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "italic");
    selectContents(diary);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    expect(diary.querySelector("em")?.textContent).toBe("italic");
    selectContents(diary.querySelector("em")!);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    expect(diary.querySelector("em")).toBeNull();
    expect(diary.textContent).toBe("italic");

    unmount();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const strikeDiary = screen.getByLabelText("Diary");
    await user.type(strikeDiary, "strike");
    selectContents(strikeDiary);
    await user.click(screen.getByRole("button", { name: "Strikethrough selection" }));
    expect(strikeDiary.querySelector("del")?.textContent).toBe("strike");
    selectContents(strikeDiary.querySelector("del")!);
    await user.click(screen.getByRole("button", { name: "Strikethrough selection" }));
    expect(strikeDiary.querySelector("del")).toBeNull();
    expect(strikeDiary.textContent).toBe("strike");
  });

  it("keeps italic formatting when bold is toggled off from mixed formatting", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "mixed");
    selectContents(diary);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    selectContents(diary.querySelector("strong")!);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));

    expect(diary.querySelector("strong em")?.textContent).toBe("mixed");
    selectContents(diary.querySelector("em")!);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));

    expect(diary.querySelector("strong")).toBeNull();
    expect(diary.querySelector("em")?.textContent).toBe("mixed");
  });

  it("toggles bold off only for the selected text and keeps surrounding bold text", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "quiet morning");
    selectContents(diary);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));

    selectText(textNodeContaining(diary, "quiet morning"), 0, 5);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));

    expect(diary.textContent).toBe("quiet morning");
    expect(diary.querySelector("strong")?.textContent).toBe(" morning");
  });

  it("toggles bold off for selected nested content without removing its other formatting", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={{ ...event, description: "**before *inner* [link](https://example.com) after**" }} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");

    selectContents(diary.querySelector("em")!);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));

    expect(diary.querySelector("em")?.textContent).toBe("inner");
    const boldSegments = Array.from(diary.querySelectorAll("strong")).map((element) => element.textContent);
    expect(boldSegments).toContain("before ");
    expect(boldSegments).toContain("link");
    expect(boldSegments).toContain(" after");
    expect(screen.getByRole("link", { name: "link" }).closest("strong")?.textContent).toBe("link");
    expect(diary.querySelector("em")?.closest("strong")).toBeNull();
  });

  it("adds a safe diary link, saves it as restricted Markdown, and reopens it visually", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "example");
    selectContents(diary);
    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.type(screen.getByLabelText("Link URL"), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Apply link" }));

    const link = screen.getByRole("link", { name: "example" });
    expect(link).toHaveAttribute("href", "https://example.com");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));
    await waitFor(() => expect(updateEvent).toHaveBeenCalledWith("event-1", expect.objectContaining({ description: "[example](https://example.com)" }), "\"1\""));

    unmount();
    render(<EventForm categories={[category]} event={{ ...event, description: "[example](https://example.com)" }} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByRole("link", { name: "example" })).toHaveAttribute("href", "https://example.com");
  });

  it("opens link editing in a dialog and preserves the selected editor text while the dialog has focus", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "example and notes");
    selectText(diary.firstChild!, 0, 7);

    await user.click(screen.getByRole("button", { name: "Link selection" }));

    const dialog = screen.getByRole("dialog", { name: "Add link" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByLabelText("Link URL")).toHaveFocus();
    expect(screen.getByRole("button", { name: "Apply link" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel link" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Link URL"), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Apply link" }));

    expect(screen.queryByRole("dialog", { name: "Add link" })).toBeNull();
    expect(screen.getByRole("link", { name: "example" })).toHaveAttribute("href", "https://example.com");
    expect(diary.textContent).toBe("example and notes");
  });

  it("cancels the link dialog without changing editor content", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "plain text");
    selectText(diary.firstChild!, 0, 5);

    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.type(screen.getByLabelText("Link URL"), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Cancel link" }));

    expect(screen.queryByRole("dialog", { name: "Add link" })).toBeNull();
    expect(screen.queryByRole("link", { name: "plain" })).toBeNull();
    expect(diary.textContent).toBe("plain text");
  });

  it("returns focus to the link toolbar button after the link dialog closes", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "plain text");
    selectText(diary.firstChild!, 0, 5);

    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.click(screen.getByRole("button", { name: "Cancel link" }));

    expect(screen.getByRole("button", { name: "Link selection" })).toHaveFocus();
  });

  it("keeps keyboard focus inside the link dialog", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "focus target");
    selectText(diary.firstChild!, 0, 5);

    await user.click(screen.getByRole("button", { name: "Link selection" }));

    const urlInput = screen.getByLabelText("Link URL");
    const cancelButton = screen.getByRole("button", { name: "Cancel link" });
    const applyButton = screen.getByRole("button", { name: "Apply link" });
    expect(urlInput).toHaveFocus();

    await user.tab();
    expect(cancelButton).toHaveFocus();
    await user.tab();
    expect(applyButton).toHaveFocus();
    await user.tab();
    expect(urlInput).toHaveFocus();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(applyButton).toHaveFocus();
  });

  it("stores link URLs with Markdown-sensitive characters so they reopen as safe links", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "reference");
    selectContents(diary);
    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.type(screen.getByLabelText("Link URL"), "https://example.com/a(foo)?q=1");
    await user.click(screen.getByRole("button", { name: "Apply link" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledWith("event-1", expect.objectContaining({ description: "[reference](https://example.com/a%28foo%29?q=1)" }), "\"1\""));
    unmount();
    render(<EventForm categories={[category]} event={{ ...event, description: "[reference](https://example.com/a%28foo%29?q=1)" }} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByRole("link", { name: "reference" })).toHaveAttribute("href", "https://example.com/a%28foo%29?q=1");
  });

  it("reopens safe links with paired Markdown formatting characters in the URL without corrupting them", () => {
    render(<EventForm categories={[category]} event={{ ...event, description: "[reference](https://example.com/a*b*c)" }} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);

    expect(screen.getByRole("link", { name: "reference" })).toHaveAttribute("href", "https://example.com/a*b*c");
    expect(screen.getByLabelText("Diary").querySelector("em")).toBeNull();
  });

  it("does not turn an unsafe diary URL into an executable link", async () => {
    const user = userEvent.setup();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "unsafe");
    selectContents(diary);
    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.type(screen.getByLabelText("Link URL"), "javascript:alert(1)");
    await user.click(screen.getByRole("button", { name: "Apply link" }));

    expect(screen.queryByRole("link", { name: "unsafe" })).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("Use an http or https link.");
    expect(diary.textContent).toBe("unsafe");
  });

  it("neutralizes manually typed unsafe Markdown links and raw HTML before saving", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    const paste = createEvent.paste(diary, { clipboardData: { getData: () => "[unsafe](javascript:alert) <script>bad</script>" } });
    fireEvent(diary, paste);
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledWith("event-1", expect.objectContaining({
      description: "\\[unsafe\\]\\(javascript:alert\\) &lt;script&gt;bad&lt;/script&gt;",
    }), "\"1\""));
  });

  it("round-trips bold italic strikethrough and link formatting through Markdown storage", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "bold italic strike link");
    selectText(textNodeContaining(diary, "bold"), 0, 4);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    selectText(textNodeContaining(diary, " italic"), 1, 7);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    selectText(textNodeContaining(diary, " strike"), 1, 7);
    await user.click(screen.getByRole("button", { name: "Strikethrough selection" }));
    selectText(textNodeContaining(diary, " link"), 1, 5);
    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.type(screen.getByLabelText("Link URL"), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Apply link" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledWith("event-1", expect.objectContaining({ description: "**bold** *italic* ~~strike~~ [link](https://example.com)" }), "\"1\""));
    unmount();
    render(<EventForm categories={[category]} event={{ ...event, description: "**bold** *italic* ~~strike~~ [link](https://example.com)" }} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByText("bold").tagName.toLowerCase()).toBe("strong");
    expect(screen.getByText("italic").tagName.toLowerCase()).toBe("em");
    expect(screen.getByText("strike").tagName.toLowerCase()).toBe("del");
    expect(screen.getByRole("link", { name: "link" })).toHaveAttribute("href", "https://example.com");
  });

  it("round-trips multiline link followed by italic text without leaking Markdown delimiters", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    diary.innerHTML = "normal text<br>LC<br>哈士奇";
    fireEvent.input(diary);

    selectText(textNodeContaining(diary, "LC"), 0, 2);
    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.type(screen.getByLabelText("Link URL"), "https://example.com/lc");
    await user.click(screen.getByRole("button", { name: "Apply link" }));

    const italicNode = textNodeContaining(diary, "哈士奇");
    const italicRange = document.createRange();
    italicRange.setStartBefore(italicNode.previousSibling!);
    italicRange.setEnd(italicNode, 3);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(italicRange);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledTimes(1));
    const savedDescription = updateEvent.mock.calls[0][1].description;
    expect(savedDescription).toBe("normal text\n[LC](https://example.com/lc)\n*哈士奇*");

    unmount();
    render(<MarkdownDescription source={savedDescription} />);
    expect(screen.getByText("normal text")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "LC" })).toHaveAttribute("href", "https://example.com/lc");
    expect(screen.getByText("哈士奇").tagName.toLowerCase()).toBe("em");
    expect(screen.getByTestId("markdown-description")).not.toHaveTextContent("*");

    cleanup();
    const reopenedUpdate = vi.fn().mockResolvedValue(event);
    render(<EventForm categories={[category]} event={{ ...event, description: savedDescription }} updateEvent={reopenedUpdate} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const reopenedDiary = screen.getByLabelText("Diary");
    expect(screen.getByRole("link", { name: "LC" })).toHaveAttribute("href", "https://example.com/lc");
    expect(screen.getByText("哈士奇").tagName.toLowerCase()).toBe("em");
    expect(reopenedDiary).not.toHaveTextContent("*");
    expect(reopenedDiary.textContent).toBe("normal textLC哈士奇");
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(reopenedUpdate).toHaveBeenCalledTimes(1));
    expect(reopenedUpdate.mock.calls[0][1].description).toBe("normal text\n[LC](https://example.com/lc)\n*哈士奇*");
  });

  it("keeps user-typed literal Markdown markers literal after save render and reopen", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    diary.textContent = "literal *stars* and [brackets]";
    fireEvent.input(diary);
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledTimes(1));
    const savedDescription = updateEvent.mock.calls[0][1].description;
    expect(savedDescription).toBe("literal \\*stars\\* and \\[brackets\\]");

    unmount();
    render(<MarkdownDescription source={savedDescription} />);
    expect(screen.getByTestId("markdown-description")).toHaveTextContent("literal *stars* and [brackets]");
    expect(screen.queryByText("stars")?.tagName.toLowerCase()).not.toBe("em");

    cleanup();
    const reopenedUpdate = vi.fn().mockResolvedValue(event);
    render(<EventForm categories={[category]} event={{ ...event, description: savedDescription }} updateEvent={reopenedUpdate} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const reopenedDiary = screen.getByLabelText("Diary");
    expect(reopenedDiary).toHaveTextContent("literal *stars* and [brackets]");
    expect(reopenedDiary.querySelector("em")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(reopenedUpdate).toHaveBeenCalledTimes(1));
    expect(reopenedUpdate.mock.calls[0][1].description).toBe(savedDescription);
  });

  it("rejects diary descriptions over the 10000 character limit before saving", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    diary.textContent = "a".repeat(10001);
    fireEvent.input(diary);

    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Diary must be 10000 characters or fewer.");
    expect(updateEvent).not.toHaveBeenCalled();
  });

  it("round-trips multiple formatted lines with standalone italic combined formats and Markdown-sensitive link URLs", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    diary.innerHTML = "plain<br>italic<br>combo<br>strike italic<br>reference";
    fireEvent.input(diary);

    selectText(textNodeContaining(diary, "italic"), 0, 6);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    selectText(textNodeContaining(diary, "combo"), 0, 5);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    selectContents(diary.querySelector("strong")!);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    selectText(textNodeContaining(diary, "strike italic"), 0, 13);
    await user.click(screen.getByRole("button", { name: "Strikethrough selection" }));
    selectContents(diary.querySelector("del")!);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    selectText(textNodeContaining(diary, "reference"), 0, 9);
    await user.click(screen.getByRole("button", { name: "Link selection" }));
    await user.type(screen.getByLabelText("Link URL"), "https://example.com/a(foo)?q=1&x=*y*");
    await user.click(screen.getByRole("button", { name: "Apply link" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledTimes(1));
    const savedDescription = updateEvent.mock.calls[0][1].description;
    expect(savedDescription).toBe("plain\n*italic*\n***combo***\n~~*strike italic*~~\n[reference](https://example.com/a%28foo%29?q=1&x=*y*)");

    unmount();
    render(<EventForm categories={[category]} event={{ ...event, description: savedDescription }} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const reopenedDiary = screen.getByLabelText("Diary");
    expect(reopenedDiary.querySelector("em")?.textContent).toBe("italic");
    expect(reopenedDiary.querySelector("strong em")?.textContent).toBe("combo");
    expect(reopenedDiary.querySelector("del em")?.textContent).toBe("strike italic");
    expect(screen.getByRole("link", { name: "reference" })).toHaveAttribute("href", "https://example.com/a%28foo%29?q=1&x=*y*");
    expect(reopenedDiary).not.toHaveTextContent("***");
    expect(reopenedDiary).not.toHaveTextContent("~~");
  });

  it("formats selections visually with italic and strikethrough without raw markers", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "italic strike");
    const range = document.createRange();
    range.setStart(diary.firstChild!, 0);
    range.setEnd(diary.firstChild!, 6);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
    await user.click(screen.getByRole("button", { name: "Italic selection" }));
    expect(diary.querySelector("em")?.textContent).toBe("italic");
    expect(diary.textContent).not.toContain("*");

    unmount();
    render(<EventForm categories={[category]} createEvent={vi.fn()} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const strikeDiary = screen.getByLabelText("Diary");
    await user.type(strikeDiary, "strike");
    const strikeRange = document.createRange();
    strikeRange.selectNodeContents(strikeDiary);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(strikeRange);
    await user.click(screen.getByRole("button", { name: "Strikethrough selection" }));

    expect(strikeDiary.querySelector("del")?.textContent).toBe("strike");
    expect(strikeDiary.textContent).not.toContain("~~");
  });

  it("serializes visual formatting to restricted Markdown on save", async () => {
    const updateEvent = vi.fn().mockResolvedValue(event);
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={event} updateEvent={updateEvent} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    await user.type(diary, "bold");
    const range = document.createRange();
    range.selectNodeContents(diary);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
    await user.click(screen.getByRole("button", { name: "Bold selection" }));
    await user.click(screen.getByRole("button", { name: "Save Pawprint" }));

    await waitFor(() => expect(updateEvent).toHaveBeenCalledWith("event-1", expect.objectContaining({ description: "**bold**" }), "\"1\""));
  });

  it("escapes unsafe HTML in the visual editor", () => {
    render(<EventForm categories={[category]} event={{ ...event, description: "<script>window.bad = true</script>" }} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    expect(diary.querySelector("script")).toBeNull();
    expect(diary.textContent).toContain("<script>");
    expect((window as Window & { bad?: boolean }).bad).toBeUndefined();
  });

  it("prevents rich HTML paste from entering the live diary editor", () => {
    render(<EventForm categories={[category]} uploadEventMedia={vi.fn()} onSaved={vi.fn()} />);
    const diary = screen.getByLabelText("Diary");
    const paste = createEvent.paste(diary, { clipboardData: { getData: (type: string) => type === "text/plain" ? "safe text" : "<img src=x onerror=alert(1)>" } });
    fireEvent(diary, paste);
    expect(paste.defaultPrevented).toBe(true);
    expect(diary.querySelector("img")).toBeNull();
  });

  it("cancels an edit without patching, uploading, or deleting queued existing media", async () => {
    const savedMedia = { id: "media-1", display_order: 1, mime_type: "image/jpeg", file_size: 10, created_at: "2026-09-09T00:00:00Z" };
    const updateEvent = vi.fn();
    const uploadEventMedia = vi.fn();
    const deleteMedia = vi.fn();
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(<EventForm categories={[category]} event={{ ...event, media: [savedMedia] }} updateEvent={updateEvent} uploadEventMedia={uploadEventMedia} deleteMedia={deleteMedia} fetchMediaObjectUrl={vi.fn().mockResolvedValue("blob:media")} onSaved={vi.fn()} onCancel={onCancel} />);
    await screen.findByRole("img", { name: "Saved image 1" });
    await user.upload(screen.getByLabelText("Images"), image("pending.jpg"));
    await user.click(screen.getByRole("button", { name: "Remove saved image 1" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(updateEvent).not.toHaveBeenCalled();
    expect(uploadEventMedia).not.toHaveBeenCalled();
    expect(deleteMedia).not.toHaveBeenCalled();
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
