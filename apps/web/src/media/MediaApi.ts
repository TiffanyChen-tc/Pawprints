import { apiBlobRequest, apiRequest } from "../api/client";
export interface Media { id: string; display_order: number; mime_type: string; file_size: number; created_at: string }
export async function uploadEventMedia(eventId: string, files: File[]) { const form = new FormData(); files.forEach((file) => form.append("files", file)); return (await apiRequest<Media[]>(`/api/v1/media/events/${eventId}`, { method: "POST", body: form })).data; }
export async function getEventMedia(eventId: string) { const { data } = await apiRequest<Media[] | { items: Media[] }>(`/api/v1/media/events/${eventId}`); return Array.isArray(data) ? data : data.items; }
export async function deleteMedia(mediaId: string) { await apiRequest<void>(`/api/v1/media/${mediaId}`, { method: "DELETE" }); }
export async function fetchMediaObjectUrl(id: string) { return URL.createObjectURL(await apiBlobRequest(`/api/v1/media/${id}`)); }
export function revokeMediaObjectUrl(url: string) { URL.revokeObjectURL(url); }
