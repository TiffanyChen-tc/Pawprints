import { afterEach, describe, expect, it, vi } from "vitest";

import { configureApiClient, createApiClient } from "../api/client";
import { getActivityCounts } from "./AnalyticsApi";

describe("getActivityCounts", () => {
  afterEach(() => vi.restoreAllMocks());

  it("serializes only the public analytics endpoint and allowed query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ start_date: "2026-09-01", end_date: "2026-09-30", grouping: "none", items: [] }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const restore = configureApiClient(createApiClient({ fetch: fetchMock, getAccessToken: () => "access-token", refresh: vi.fn(), onAuthFailure: vi.fn() }));

    await getActivityCounts({
      start_date: "2026-09-01",
      end_date: "2026-09-30",
      grouping: "month",
      category_id: "cat-1",
      user_id: "spoofed",
    } as never);

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30&grouping=month&category_id=cat-1",
    );
    restore();
  });
});
