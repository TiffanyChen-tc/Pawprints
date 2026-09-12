import { afterEach, describe, expect, it, vi } from "vitest";

import { configureApiClient, createApiClient } from "../api/client";
import { deleteMedia, fetchMediaObjectUrl } from "./MediaApi";

describe("fetchMediaObjectUrl", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses the authenticated API client to retrieve a private Blob without a tokenized URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("image", { status: 200, headers: { "Content-Type": "image/png" } }));
    const restore = configureApiClient(createApiClient({
      fetch: fetchMock,
      getAccessToken: () => "runtime-access-token",
      refresh: vi.fn(),
      onAuthFailure: vi.fn(),
    }));
    const objectUrl = vi.fn().mockReturnValue("blob:private");
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: objectUrl });

    await expect(fetchMediaObjectUrl("media-1")).resolves.toBe("blob:private");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/media/media-1",
      expect.objectContaining({ credentials: "include", headers: expect.any(Headers) }),
    );
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("Authorization")).toBe("Bearer runtime-access-token");
    expect(fetchMock.mock.calls[0]?.[0]).not.toContain("runtime-access-token");
    restore();
  });

  it("deletes media through the public authenticated Media API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const restore = configureApiClient(createApiClient({
      fetch: fetchMock,
      getAccessToken: () => "runtime-access-token",
      refresh: vi.fn(),
      onAuthFailure: vi.fn(),
    }));

    await deleteMedia("media-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/media/media-1",
      expect.objectContaining({ credentials: "include", method: "DELETE" }),
    );
    expect(fetchMock.mock.calls[0]?.[0]).not.toContain("/internal/");
    restore();
  });
});
