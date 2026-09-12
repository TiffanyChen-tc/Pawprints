import { apiRequest } from "../api/client";
import type { Event, Mood } from "../events/EventApi";

export interface SearchFilters {
  keyword?: string;
  start_date?: string;
  end_date?: string;
  category_id?: string;
  mood?: Mood;
  location?: string;
}

export async function searchEvents(filters: SearchFilters) {
  const query = new URLSearchParams();
  for (const key of ["keyword", "start_date", "end_date", "category_id", "mood", "location"] as const) {
    const value = filters[key];
    if (value) query.set(key, value);
  }
  const suffix = query.size ? `?${query.toString()}` : "";
  const response = await apiRequest<{ items: Omit<Event, "etag">[] }>(`/api/v1/events/search${suffix}`);
  return response.data.items.map((event) => ({
    ...event,
    etag: response.headers.get("ETag") ?? `\"${event.version}\"`,
  }));
}
