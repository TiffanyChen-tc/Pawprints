import { render, screen } from "@testing-library/react";
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
