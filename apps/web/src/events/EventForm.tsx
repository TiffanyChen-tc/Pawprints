import { useEffect, useRef, useState } from "react";
import { Bold, Italic, Plus, Strikethrough } from "lucide-react";

import { ApiError } from "../api/client";
import MediaCarousel from "../media/MediaCarousel";
import { deleteMedia as defaultDeleteMedia, fetchMediaObjectUrl as defaultFetchMediaObjectUrl, revokeMediaObjectUrl as defaultRevokeMediaObjectUrl, uploadEventMedia as defaultUpload, type Media } from "../media/MediaApi";
import { createCategory as defaultCreateCategory, createEvent as defaultCreate, updateEvent as defaultUpdate, type Category, type Event, type EventInput, type Mood } from "./EventApi";

const moods: Mood[] = ["great", "good", "neutral", "low", "bad"];
const allowedImageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);

function localDateTime() {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function eventDateTime(event: Event) {
  const values = new Intl.DateTimeFormat("en-CA", { timeZone: event.timezone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(event.occurred_at));
  const part = (name: string) => values.find((value) => value.type === name)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

type EventFormProps = {
  categories: Category[];
  createCategory?: (name: string) => Promise<Category>;
  createEvent?: (input: EventInput) => Promise<Event>;
  updateEvent?: (id: string, input: Partial<EventInput>, etag: string) => Promise<Event>;
  uploadEventMedia?: (id: string, files: File[]) => Promise<Media[]>;
  deleteMedia?: (id: string) => Promise<void>;
  fetchMediaObjectUrl?: (id: string) => Promise<string>;
  revokeMediaObjectUrl?: (url: string) => void;
  onSaved: (event: Event) => void;
  onCompleted?: () => void;
  onCategoryCreated?: (category: Category) => void;
  onConflict?: (event: Event) => void;
  event?: Event;
};

type PendingImage = { id: string; file: File; previewUrl: string };

function SavedMediaPreview({ media, fetchMediaObjectUrl, revokeMediaObjectUrl, onRemove }: { media: Media; fetchMediaObjectUrl: (id: string) => Promise<string>; revokeMediaObjectUrl: (url: string) => void; onRemove: (media: Media) => void }) {
  const [url, setUrl] = useState("");

  useEffect(() => {
    let active = true;
    let loaded = "";
    void fetchMediaObjectUrl(media.id).then((next) => {
      loaded = next;
      if (active) setUrl(next);
      else revokeMediaObjectUrl(next);
    }).catch(() => {
      if (active) setUrl("");
    });
    return () => {
      active = false;
      if (loaded) revokeMediaObjectUrl(loaded);
    };
  }, [fetchMediaObjectUrl, media.id, revokeMediaObjectUrl]);

  return <div className="image-preview">
    {url && <img src={url} alt={`Saved image ${media.display_order}`} />}
    <button type="button" aria-label={`Remove saved image ${media.display_order}`} onClick={() => onRemove(media)}>Remove</button>
  </div>;
}

export default function EventForm({ categories, createCategory = defaultCreateCategory, createEvent = defaultCreate, updateEvent = defaultUpdate, uploadEventMedia = defaultUpload, deleteMedia = defaultDeleteMedia, fetchMediaObjectUrl = defaultFetchMediaObjectUrl, revokeMediaObjectUrl = defaultRevokeMediaObjectUrl, onSaved, onCompleted, onCategoryCreated, onConflict, event }: EventFormProps) {
  const [availableCategories, setAvailableCategories] = useState(categories);
  const [title, setTitle] = useState(event?.title ?? "");
  const [categoryId, setCategoryId] = useState(event?.category_id ?? "");
  const [newCategory, setNewCategory] = useState("");
  const [dateTime, setDateTime] = useState(event ? eventDateTime(event) : localDateTime());
  const [timezone, setTimezone] = useState(event?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [description, setDescription] = useState(event?.description ?? "");
  const [mood, setMood] = useState(event?.mood ?? "");
  const [location, setLocation] = useState(event?.location_name ?? "");
  const [latitude, setLatitude] = useState(event?.latitude?.toString() ?? "");
  const [longitude, setLongitude] = useState(event?.longitude?.toString() ?? "");
  const [files, setFiles] = useState<PendingImage[]>([]);
  const [failed, setFailed] = useState<PendingImage[]>([]);
  const [existingMedia, setExistingMedia] = useState<Media[]>(event?.media ?? []);
  const [uploadedMedia, setUploadedMedia] = useState<Media[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Event | null>(null);
  const [eventDirtyAfterSave, setEventDirtyAfterSave] = useState(false);
  const diaryRef = useRef<HTMLTextAreaElement>(null);
  const previews = useRef<string[]>([]);

  useEffect(() => { previews.current = files.map((item) => item.previewUrl); }, [files]);
  useEffect(() => () => previews.current.forEach((url) => URL.revokeObjectURL(url)), []);

  const input = (): EventInput => ({
    title,
    category_id: categoryId,
    local_datetime: dateTime,
    timezone,
    description: description || null,
    mood: (mood || null) as Mood | null,
    location_name: location || null,
    latitude: latitude === "" ? null : Number(latitude),
    longitude: longitude === "" ? null : Number(longitude),
  });

  const updateField = (setter: (value: string) => void, value: string) => {
    setter(value);
    if (saved) setEventDirtyAfterSave(true);
  };

  const addCategory = async () => {
    const name = newCategory.trim();
    if (!name) return;
    setError("");
    try {
      const category = await createCategory(name);
      setAvailableCategories((items) => [...items, category]);
      setCategoryId(category.id);
      setNewCategory("");
      onCategoryCreated?.(category);
    } catch {
      setError("Could not add this category. Please try again.");
    }
  };

  const selectFiles = (selected: File[]) => {
    if (selected.some((file) => !allowedImageTypes.has(file.type))) {
      setError("Images must be JPEG, PNG, or WebP files.");
      return;
    }
    if (existingMedia.length + files.length + selected.length > 5) { setError("Select up to 5 images total."); return; }
    setError("");
    setFiles((items) => [...items, ...selected.map((file) => ({ id: crypto.randomUUID(), file, previewUrl: URL.createObjectURL(file) }))]);
  };

  const removePending = (id: string) => {
    const remove = (items: PendingImage[]) => {
      const removed = items.find((item) => item.id === id);
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      return items.filter((item) => item.id !== id);
    };
    setFiles(remove);
    setFailed((items) => items.filter((item) => item.id !== id));
  };
  const removeExisting = async (media: Media) => { try { await deleteMedia(media.id); setExistingMedia((items) => items.filter((item) => item.id !== media.id)); } catch { setError("Could not remove this image. Please try again."); } };

  const upload = async (savedEvent: Event, selected: PendingImage[]) => {
    if (!selected.length) return true;
    try {
      setUploadedMedia(await uploadEventMedia(savedEvent.id, selected.map((item) => item.file)));
      const selectedIds = new Set(selected.map((item) => item.id));
      const remaining = files.filter((item) => !selectedIds.has(item.id));
      setFailed((items) => items.filter((item) => !selected.some((uploaded) => uploaded.id === item.id)));
      selected.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      setFiles(remaining);
      return remaining.length === 0;
    } catch {
      setFailed(selected);
      setError("Image upload failed. Your Pawprint was saved.");
      return false;
    }
  };

  const submit = async (retry = false) => {
    setError("");
    if (!retry && Boolean(latitude) !== Boolean(longitude)) {
      setError("Provide both latitude and longitude, or leave both blank.");
      return;
    }
    try {
      let savedEvent = saved;
      if (!retry) {
        if (savedEvent && !eventDirtyAfterSave) {
          // The event mutation already succeeded; this save completes remaining media.
        } else if (savedEvent) {
          savedEvent = await updateEvent(savedEvent.id, input(), savedEvent.etag);
          setSaved(savedEvent);
          setEventDirtyAfterSave(false);
          onSaved(savedEvent);
        } else {
          savedEvent = event ? await updateEvent(event.id, input(), event.etag) : await createEvent(input());
          setSaved(savedEvent);
          setEventDirtyAfterSave(false);
          onSaved(savedEvent);
        }
      }
      if (savedEvent && await upload(savedEvent, retry ? failed : files)) onCompleted?.();
    } catch (reason) {
      if (event && (reason instanceof ApiError ? reason.status : (reason as { status?: number }).status) === 412) {
        onConflict?.(event);
        setError("This Pawprint changed since you opened it. Review the latest version.");
      } else {
        setError("Could not save Pawprint. Please review your details and try again.");
      }
    }
  };

  const wrapSelection = (marker: string) => {
    const field = diaryRef.current;
    if (!field) return;
    const start = field.selectionStart;
    const end = field.selectionEnd;
    const selection = description.slice(start, end);
    setDescription(`${description.slice(0, start)}${marker}${selection}${marker}${description.slice(end)}`);
    if (saved) setEventDirtyAfterSave(true);
    requestAnimationFrame(() => {
      field.focus();
      field.setSelectionRange(start + marker.length, end + marker.length);
    });
  };

  return <form className="event-form" onSubmit={(formEvent) => { formEvent.preventDefault(); void submit(); }}>
    <h2>{event ? "Edit Pawprint" : "New Pawprint"}</h2>
    {error && <p role="alert" className="form-error">{error}</p>}
    {saved && <p role="status">Pawprint saved</p>}
    <label>Title<input aria-label="Title" value={title} maxLength={120} required onChange={(inputEvent) => updateField(setTitle, inputEvent.target.value)} /></label>
    <label>Category<select aria-label="Category" value={categoryId} required onChange={(inputEvent) => updateField(setCategoryId, inputEvent.target.value)}><option value="">Choose a category</option>{availableCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
    <div className="quick-category"><label>New category<input aria-label="New category" value={newCategory} maxLength={120} onChange={(inputEvent) => setNewCategory(inputEvent.target.value)} /></label><button type="button" className="secondary-button" onClick={() => void addCategory()}><Plus aria-hidden="true" size={16} /> Add category</button></div>
    <label>Date and time<input aria-label="Date and time" type="datetime-local" value={dateTime} required onChange={(inputEvent) => updateField(setDateTime, inputEvent.target.value)} /></label>
    <label>Timezone<input aria-label="Timezone" value={timezone} required onChange={(inputEvent) => updateField(setTimezone, inputEvent.target.value)} /></label>
    <label>Mood<select aria-label="Mood" value={mood} onChange={(inputEvent) => updateField(setMood, inputEvent.target.value)}><option value="">No mood</option>{moods.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
    <div className="diary-field"><label htmlFor="event-description">Diary</label><div className="markdown-toolbar"><button type="button" className="icon-button" aria-label="Bold selection" title="Bold selection" onClick={() => wrapSelection("**")}><Bold aria-hidden="true" size={16} /></button><button type="button" className="icon-button" aria-label="Italic selection" title="Italic selection" onClick={() => wrapSelection("*")}><Italic aria-hidden="true" size={16} /></button><button type="button" className="icon-button" aria-label="Strikethrough selection" title="Strikethrough selection" onClick={() => wrapSelection("~~")}><Strikethrough aria-hidden="true" size={16} /></button></div><textarea id="event-description" ref={diaryRef} aria-label="Diary" value={description} maxLength={10000} onChange={(inputEvent) => updateField(setDescription, inputEvent.target.value)} /></div>
    <label>Location<input aria-label="Location" value={location} onChange={(inputEvent) => updateField(setLocation, inputEvent.target.value)} /></label>
    <div className="coordinate-fields"><label>Latitude<input aria-label="Latitude" type="number" min="-90" max="90" step="any" value={latitude} onChange={(inputEvent) => updateField(setLatitude, inputEvent.target.value)} /></label><label>Longitude<input aria-label="Longitude" type="number" min="-180" max="180" step="any" value={longitude} onChange={(inputEvent) => updateField(setLongitude, inputEvent.target.value)} /></label></div>
    <label>Images<input aria-label="Images" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(inputEvent) => { selectFiles(Array.from(inputEvent.target.files ?? [])); inputEvent.target.value = ""; }} /></label>
    <p className="field-hint">{existingMedia.length + files.length} of 5 images selected.</p>
    <div className="image-previews">{existingMedia.map((item) => <SavedMediaPreview key={item.id} media={item} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} onRemove={(media) => void removeExisting(media)} />)}{files.map((item) => <div key={item.id} className="image-preview"><img src={item.previewUrl} alt={`${item.file.name} thumbnail`} /><button type="button" aria-label={`Remove ${item.file.name}`} onClick={() => removePending(item.id)}>Remove</button></div>)}</div>
    <button type="submit">Save Pawprint</button>
    {failed.length > 0 && <button type="button" className="secondary-button" onClick={() => void submit(true)}>Retry image upload</button>}
    {uploadedMedia.length > 0 && <MediaCarousel media={uploadedMedia} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />}
  </form>;
}
