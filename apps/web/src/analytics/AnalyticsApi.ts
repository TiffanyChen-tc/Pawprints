import { apiRequest } from "../api/client";

export type AnalyticsGrouping = "none" | "week" | "month";

export interface AnalyticsQuery {
  start_date: string;
  end_date: string;
  category_id?: string;
  grouping: AnalyticsGrouping;
}

export interface CategoryCount { category_id: string; category_name: string; count: number }
export interface AnalyticsBucket { bucket_start_date: string; items: CategoryCount[] }
export type ActivityCounts =
  | { start_date: string; end_date: string; grouping: "none"; items: CategoryCount[] }
  | { start_date: string; end_date: string; grouping: "week" | "month"; buckets: AnalyticsBucket[] };

export async function getActivityCounts(query: AnalyticsQuery) {
  const params = new URLSearchParams({ start_date: query.start_date, end_date: query.end_date, grouping: query.grouping });
  if (query.category_id) params.set("category_id", query.category_id);
  return (await apiRequest<ActivityCounts>(`/api/v1/analytics/activity-counts?${params.toString()}`)).data;
}
