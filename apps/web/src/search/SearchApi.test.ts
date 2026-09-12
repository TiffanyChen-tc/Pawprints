import { afterEach, describe, expect, it, vi } from "vitest";

import { configureApiClient, createApiClient } from "../api/client";
import { searchEvents } from "./SearchApi";

describe("searchEvents", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends only supported populated filters to the public search endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const restore = configureApiClient(createApiClient({ fetch: fetchMock, getAccessToken: () => "access-token", refresh: vi.fn(), onAuthFailure: vi.fn() }));

    await searchEvents({ keyword: "morning walk", start_date: "2026-09-01", end_date: "2026-09-09", category_id: "cat-1", mood: "good", location: "park", user_id: "spoofed" } as never);

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/events/search?keyword=morning+walk&start_date=2026-09-01&end_date=2026-09-09&category_id=cat-1&mood=good&location=park");
    restore();
  });
});
