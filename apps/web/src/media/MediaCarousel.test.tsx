import { fireEvent, render, screen } from "@testing-library/react";
import { waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MediaCarousel from "./MediaCarousel";

it("fetches private media as blobs and revokes object URLs on unmount", async () => {
  const fetchMediaObjectUrl = vi.fn().mockResolvedValue("blob:private");
  const revokeMediaObjectUrl = vi.fn();
  const { unmount } = render(<MediaCarousel media={[{ id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />);
  expect(await screen.findByRole("img")).toHaveAttribute("src", "blob:private");
  unmount();
  expect(revokeMediaObjectUrl).toHaveBeenCalledWith("blob:private");
});

it("revokes replaced object URLs when its media changes", async () => {
  const fetchMediaObjectUrl = vi.fn().mockImplementation(async (id: string) => `blob:${id}`);
  const revokeMediaObjectUrl = vi.fn();
  const { rerender } = render(<MediaCarousel media={[{ id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />);
  await screen.findByRole("img", { name: "Pawprint image 1" });
  rerender(<MediaCarousel media={[{ id: "m2", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />);
  expect(await screen.findByRole("img", { name: "Pawprint image 1" })).toHaveAttribute("src", "blob:m2");
  expect(revokeMediaObjectUrl).toHaveBeenCalledWith("blob:m1");
});

it("revokes already-created object URLs when a later fetch fails", async () => {
  const fetchMediaObjectUrl = vi
    .fn()
    .mockResolvedValueOnce("blob:m1")
    .mockRejectedValueOnce(new Error("media unavailable"));
  const revokeMediaObjectUrl = vi.fn();

  render(
    <MediaCarousel
      media={[
        { id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" },
        { id: "m2", display_order: 2, mime_type: "image/jpeg", file_size: 100, created_at: "2026-09-09T00:00:00Z" },
      ]}
      fetchMediaObjectUrl={fetchMediaObjectUrl}
      revokeMediaObjectUrl={revokeMediaObjectUrl}
    />,
  );

  await waitFor(() => expect(revokeMediaObjectUrl).toHaveBeenCalledWith("blob:m1"));
});

it("revokes object URLs created after an earlier fetch has already failed", async () => {
  let resolveDelayed: ((url: string) => void) | undefined;
  const delayedUrl = new Promise<string>((resolve) => {
    resolveDelayed = resolve;
  });
  const fetchMediaObjectUrl = vi
    .fn()
    .mockReturnValueOnce(delayedUrl)
    .mockRejectedValueOnce(new Error("media unavailable"));
  const revokeMediaObjectUrl = vi.fn();

  render(
    <MediaCarousel
      media={[
        { id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" },
        { id: "m2", display_order: 2, mime_type: "image/jpeg", file_size: 100, created_at: "2026-09-09T00:00:00Z" },
      ]}
      fetchMediaObjectUrl={fetchMediaObjectUrl}
      revokeMediaObjectUrl={revokeMediaObjectUrl}
    />,
  );

  await waitFor(() => expect(fetchMediaObjectUrl).toHaveBeenCalledTimes(2));
  resolveDelayed?.("blob:m1");

  await waitFor(() => expect(revokeMediaObjectUrl).toHaveBeenCalledWith("blob:m1"));
});

it("opens an authenticated image in a viewer and closes it with the close control or Escape", async () => {
  const { user } = { user: (await import("@testing-library/user-event")).default.setup() };
  const revokeMediaObjectUrl = vi.fn();
  render(<MediaCarousel media={[{ id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]} fetchMediaObjectUrl={vi.fn().mockResolvedValue("blob:private")} revokeMediaObjectUrl={revokeMediaObjectUrl} />);
  await user.click(await screen.findByRole("button", { name: "Open image 1" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Close image viewer" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Open image 1" }));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("closes the viewer when media replacement revokes the active object URL", async () => {
  const { user } = { user: (await import("@testing-library/user-event")).default.setup() };
  const fetchMediaObjectUrl = vi.fn().mockImplementation(async (id: string) => `blob:${id}`);
  const revokeMediaObjectUrl = vi.fn();
  const { rerender } = render(<MediaCarousel media={[{ id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />);

  await user.click(await screen.findByRole("button", { name: "Open image 1" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();

  rerender(<MediaCarousel media={[{ id: "m2", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />);

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await waitFor(() => expect(revokeMediaObjectUrl).toHaveBeenCalledWith("blob:m1"));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("clears stale viewer and thumbnails during a same-id media refresh until the new blob resolves", async () => {
  const { user } = { user: (await import("@testing-library/user-event")).default.setup() };
  let resolveRefresh: ((url: string) => void) | undefined;
  const fetchMediaObjectUrl = vi
    .fn()
    .mockResolvedValueOnce("blob:m1-old")
    .mockReturnValueOnce(new Promise<string>((resolve) => { resolveRefresh = resolve; }));
  const revokeMediaObjectUrl = vi.fn();
  const first = { id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" };
  const refreshed = { ...first };
  const { rerender } = render(<MediaCarousel media={[first]} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />);

  await user.click(await screen.findByRole("button", { name: "Open image 1" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();

  rerender(<MediaCarousel media={[refreshed]} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />);

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.queryByRole("img", { name: "Pawprint image 1" })).not.toBeInTheDocument();

  resolveRefresh?.("blob:m1-new");
  expect(await screen.findByRole("img", { name: "Pawprint image 1" })).toHaveAttribute("src", "blob:m1-new");
});
