import { apiRequest } from "../api/client";

export interface Category { id: string; name: string; version: number }
export interface Event { id: string; title: string; category_id: string; category_name: string; description: string | null; mood: string | null; location_name: string | null; latitude: number | null; longitude: number | null; occurred_at: string; timezone: string; local_date: string; version: number; etag: string; media?: import("../media/MediaApi").Media[] }
export type Mood = "great" | "good" | "neutral" | "low" | "bad";
export interface EventInput { title: string; category_id: string; local_datetime: string; timezone: string; description?: string | null; mood?: Mood | null; location_name?: string | null; latitude?: number | null; longitude?: number | null }
function withEtag(event: Omit<Event, "etag">, headers: Headers): Event { return { ...event, etag: headers.get("ETag") ?? `\"${event.version}\"` }; }
export async function getTimeline(date: string) { const r = await apiRequest<{ items: Omit<Event, "etag">[] }>(`/api/v1/events/timeline?date=${encodeURIComponent(date)}`); return r.data.items.map((event) => withEtag(event, r.headers)); }
export async function getCategories() { return (await apiRequest<{ items: Category[] }>("/api/v1/categories")).data.items; }
export async function createCategory(name: string) { return (await apiRequest<Category>("/api/v1/categories", { method: "POST", body: JSON.stringify({ name }) })).data; }
export async function createEvent(input: EventInput) { const r = await apiRequest<Omit<Event, "etag">>("/api/v1/events", { method: "POST", body: JSON.stringify(input) }); return withEtag(r.data, r.headers); }
export async function getEvent(id: string) { const r = await apiRequest<Omit<Event, "etag">>(`/api/v1/events/${id}`); return withEtag(r.data, r.headers); }
export async function updateEvent(id: string, input: Partial<EventInput>, etag: string) { const r = await apiRequest<Omit<Event, "etag">>(`/api/v1/events/${id}`, { method: "PATCH", headers: { "If-Match": etag }, body: JSON.stringify(input) }); return withEtag(r.data, r.headers); }
export async function deleteEvent(id: string, etag: string) { await apiRequest<void>(`/api/v1/events/${id}`, { method: "DELETE", headers: { "If-Match": etag } }); }
