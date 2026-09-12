import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Bold, Italic, Link, Plus, Strikethrough } from "lucide-react";

import { ApiError } from "../api/client";
import MediaCarousel from "../media/MediaCarousel";
import { deleteMedia as defaultDeleteMedia, fetchMediaObjectUrl as defaultFetchMediaObjectUrl, revokeMediaObjectUrl as defaultRevokeMediaObjectUrl, uploadEventMedia as defaultUpload, type Media } from "../media/MediaApi";
import { createCategory as defaultCreateCategory, createEvent as defaultCreate, updateEvent as defaultUpdate, type Category, type Event, type EventInput, type Mood } from "./EventApi";

const moods: Mood[] = ["great", "good", "neutral", "low", "bad"];
const allowedImageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const DIARY_MAX_LENGTH = 10000;

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
  onCancel?: () => void;
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

function escapeHtml(source: string) {
  return source.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function safeLinkUrl(value: string) {
  const trimmed = value.trim();
  try {
    const url = new URL(trimmed);
    return url.protocol === "http:" || url.protocol === "https:" ? trimmed : null;
  } catch {
    return null;
  }
}

function markdownLinkDestination(value: string) {
  return value.replace(/\\/g, "%5C").replace(/\(/g, "%28").replace(/\)/g, "%29");
}

function escapeMarkdownText(value: string) {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/\*/g, "\\*")
    .replace(/_/g, "\\_")
    .replace(/~/g, "\\~")
    .replace(/\[/g, "\\[")
    .replace(/\]/g, "\\]")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");
}

function wrapMarkdownInline(content: string, opening: string, closing = opening) {
  return content.split(/(\n+)/).map((part) => part.includes("\n") || part === "" ? part : `${opening}${part}${closing}`).join("");
}

function sanitizeMarkdownDescription(value: string) {
  return value
    .replace(/\[([^\]]+)\]\(([^)]*)\)/g, (_match, text: string, href: string) => {
      const safe = safeLinkUrl(href);
      return safe ? `[${text}](${markdownLinkDestination(safe)})` : text;
    })
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function editorHtml(source: string) {
  const links: string[] = [];
  const literals: string[] = [];
  const protectLiteral = (_match: string, literal: string) => {
    const token = `PAWPRINTS_LITERAL_${literals.length}`;
    literals.push(escapeHtml(literal));
    return token;
  };
  const html = escapeHtml(source)
    .replace(/\\([\\*_\[\]()~])/g, protectLiteral)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, text: string, href: string) => {
      const safe = safeLinkUrl(href);
      if (!safe) return text;
      const token = `PAWPRINTS_LINK_${links.length}`;
      links.push(`<a href="${safe.replace(/"/g, "&quot;")}">${text}</a>`);
      return token;
    })
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/~~(.+?)~~/g, "<del>$1</del>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br>");
  return html
    .replace(/PAWPRINTS_LINK_(\d+)/g, (_match, index: string) => links[Number(index)] ?? "")
    .replace(/PAWPRINTS_LITERAL_(\d+)/g, (_match, index: string) => literals[Number(index)] ?? "");
}

function serializeEditor(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return escapeMarkdownText(node.textContent ?? "");
  const content = Array.from(node.childNodes).map(serializeEditor).join("");
  if (!(node instanceof HTMLElement)) return content;
  if (node.tagName === "STRONG" || node.tagName === "B") return wrapMarkdownInline(content, "**");
  if (node.tagName === "EM" || node.tagName === "I") return wrapMarkdownInline(content, "*");
  if (node.tagName === "DEL" || node.tagName === "S" || node.tagName === "STRIKE") return wrapMarkdownInline(content, "~~");
  if (node.tagName === "A") {
    const href = safeLinkUrl(node.getAttribute("href") ?? "");
    return href ? wrapMarkdownInline(content, "[", `](${markdownLinkDestination(href)})`) : content;
  }
  return node.tagName === "BR" ? "\n" : content;
}

function closestFormat(node: Node, boundary: HTMLElement, tag: "strong" | "em" | "del") {
  let current: Node | null = node.nodeType === Node.ELEMENT_NODE ? node : node.parentNode;
  while (current && current !== boundary.parentNode) {
    if (current instanceof HTMLElement && current.tagName.toLowerCase() === tag) return current;
    if (current === boundary) break;
    current = current.parentNode;
  }
  return null;
}

function unwrap(element: HTMLElement) {
  const parent = element.parentNode;
  if (!parent) return;
  while (element.firstChild) parent.insertBefore(element.firstChild, element);
  parent.removeChild(element);
}

function replaceRangeWithElement(range: Range, element: HTMLElement) {
  const selected = range.extractContents();
  element.append(selected);
  range.insertNode(element);
  const selection = window.getSelection();
  const nextRange = document.createRange();
  nextRange.selectNodeContents(element);
  selection?.removeAllRanges();
  selection?.addRange(nextRange);
}

function textOffset(root: Node, container: Node, offset: number) {
  const textLength = (node: Node): number => node.nodeType === Node.TEXT_NODE
    ? node.textContent?.length ?? 0
    : Array.from(node.childNodes).reduce((total, child) => total + textLength(child), 0);
  let position = 0;
  const visit = (node: Node): boolean => {
    if (node === container) {
      if (node.nodeType === Node.TEXT_NODE) position += offset;
      else position += Array.from(node.childNodes).slice(0, offset).reduce((total, child) => total + textLength(child), 0);
      return true;
    }
    for (const child of Array.from(node.childNodes)) {
      if (visit(child)) return true;
      position += textLength(child);
    }
    return false;
  };
  if (visit(root)) return position;
  return position;
}

function formattedText(tagName: string, text: string) {
  const element = document.createElement(tagName);
  element.textContent = text;
  return element;
}

function appendSegmentWithAncestors(fragment: DocumentFragment, textNode: Node, text: string, boundary: HTMLElement, includeBoundary: boolean) {
  let current: Node = fragment;
  const ancestors: HTMLElement[] = includeBoundary ? [boundary] : [];
  const innerAncestors: HTMLElement[] = [];
  let parent = textNode.parentElement;
  while (parent && parent !== boundary) {
    innerAncestors.push(parent);
    parent = parent.parentElement;
  }
  ancestors.push(...innerAncestors.reverse());
  for (const ancestor of ancestors) {
    const clone = ancestor.cloneNode(false);
    current.appendChild(clone);
    current = clone;
  }
  current.appendChild(document.createTextNode(text));
}

function unwrapSelectionFromFormat(element: HTMLElement, range: Range, tag: "strong" | "em" | "del") {
  if (!element.contains(range.startContainer) || !element.contains(range.endContainer)) return false;
  const start = textOffset(element, range.startContainer, range.startOffset);
  const end = textOffset(element, range.endContainer, range.endOffset);
  const parent = element.parentNode;
  if (!parent) return false;
  const replacement = document.createDocumentFragment();
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  let position = 0;
  let textNode = walker.nextNode();
  while (textNode) {
    const value = textNode.textContent ?? "";
    const nodeStart = position;
    const nodeEnd = nodeStart + value.length;
    const beforeEnd = Math.min(start, nodeEnd);
    const selectedStart = Math.max(start, nodeStart);
    const selectedEnd = Math.min(end, nodeEnd);
    const afterStart = Math.max(end, nodeStart);
    if (beforeEnd > nodeStart) appendSegmentWithAncestors(replacement, textNode, value.slice(0, beforeEnd - nodeStart), element, true);
    if (selectedEnd > selectedStart) appendSegmentWithAncestors(replacement, textNode, value.slice(selectedStart - nodeStart, selectedEnd - nodeStart), element, false);
    if (nodeEnd > afterStart) appendSegmentWithAncestors(replacement, textNode, value.slice(afterStart - nodeStart), element, true);
    position = nodeEnd;
    textNode = walker.nextNode();
  }
  if (!replacement.childNodes.length) return false;
  parent.insertBefore(replacement, element);
  parent.removeChild(element);
  return true;
}

export default function EventForm({ categories, createCategory = defaultCreateCategory, createEvent = defaultCreate, updateEvent = defaultUpdate, uploadEventMedia = defaultUpload, deleteMedia = defaultDeleteMedia, fetchMediaObjectUrl = defaultFetchMediaObjectUrl, revokeMediaObjectUrl = defaultRevokeMediaObjectUrl, onSaved, onCompleted, onCancel, onCategoryCreated, onConflict, event }: EventFormProps) {
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
  const [removedMedia, setRemovedMedia] = useState<Media[]>([]);
  const [uploadedMedia, setUploadedMedia] = useState<Media[]>([]);
  const [error, setError] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkEditorOpen, setLinkEditorOpen] = useState(false);
  const [saved, setSaved] = useState<Event | null>(null);
  const [eventDirtyAfterSave, setEventDirtyAfterSave] = useState(false);
  const diaryRef = useRef<HTMLDivElement>(null);
  const initialDiaryHtml = useRef(editorHtml(event?.description ?? ""));
  const previews = useRef<string[]>([]);
  const pendingLinkRange = useRef<Range | null>(null);
  const linkButtonRef = useRef<HTMLButtonElement>(null);
  const linkInputRef = useRef<HTMLInputElement>(null);
  const linkDialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => { previews.current = files.map((item) => item.previewUrl); }, [files]);
  useEffect(() => () => previews.current.forEach((url) => URL.revokeObjectURL(url)), []);
  useEffect(() => { if (linkEditorOpen) linkInputRef.current?.focus(); }, [linkEditorOpen]);

  const input = (): EventInput => ({
    title,
    category_id: categoryId,
    local_datetime: dateTime,
    timezone,
    description: description ? sanitizeMarkdownDescription(description) : null,
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
  const removeExisting = (media: Media) => {
    setExistingMedia((items) => items.filter((item) => item.id !== media.id));
    setRemovedMedia((items) => [...items, media]);
  };

  const deleteRemoved = async () => {
    if (!removedMedia.length) return true;
    try {
      await Promise.all(removedMedia.map((media) => deleteMedia(media.id)));
      setRemovedMedia([]);
      return true;
    } catch {
      setError("Could not remove this image. Please try again.");
      return false;
    }
  };

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
    if (!retry && description.length > DIARY_MAX_LENGTH) {
      setError("Diary must be 10000 characters or fewer.");
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
      if (savedEvent && await deleteRemoved() && await upload(savedEvent, retry ? failed : files)) onCompleted?.();
    } catch (reason) {
      if (event && (reason instanceof ApiError ? reason.status : (reason as { status?: number }).status) === 412) {
        onConflict?.(event);
        setError("This Pawprint changed since you opened it. Review the latest version.");
      } else {
        setError("Could not save Pawprint. Please review your details and try again.");
      }
    }
  };

  const wrapSelection = (tag: "strong" | "em" | "del") => {
    const field = diaryRef.current;
    if (!field) return;
    const selection = window.getSelection();
    const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
    if (!range || range.collapsed || !field.contains(range.commonAncestorContainer)) return;
    const existing = closestFormat(range.commonAncestorContainer, field, tag);
    if (existing) {
      if (unwrapSelectionFromFormat(existing, range, tag)) {
        setDescription(serializeEditor(field));
        if (saved) setEventDirtyAfterSave(true);
        return;
      }
    }
    const element = document.createElement(tag);
    replaceRangeWithElement(range, element);
    setDescription(serializeEditor(field));
    if (saved) setEventDirtyAfterSave(true);
  };

  const startLink = () => {
    const field = diaryRef.current;
    if (!field) return;
    const selection = window.getSelection();
    const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
    if (!range || range.collapsed || !field.contains(range.commonAncestorContainer)) return;
    pendingLinkRange.current = range.cloneRange();
    setLinkUrl("");
    setLinkEditorOpen(true);
  };

  const cancelLink = () => {
    setLinkEditorOpen(false);
    setLinkUrl("");
    pendingLinkRange.current = null;
    linkButtonRef.current?.focus();
  };

  const applyLink = () => {
    const field = diaryRef.current;
    const range = pendingLinkRange.current;
    if (!field || !range) return;
    const safe = safeLinkUrl(linkUrl);
    if (!safe) {
      setError("Use an http or https link.");
      linkInputRef.current?.focus();
      return;
    }
    const anchor = document.createElement("a");
    anchor.setAttribute("href", safe);
    try {
      replaceRangeWithElement(range, anchor);
      setDescription(serializeEditor(field));
      if (saved) setEventDirtyAfterSave(true);
      setError("");
    } catch {
      setError("Could not link this selection. Please select plain text and try again.");
    } finally {
      setLinkEditorOpen(false);
      pendingLinkRange.current = null;
      linkButtonRef.current?.focus();
    }
  };

  const trapLinkDialogFocus = (inputEvent: KeyboardEvent<HTMLDivElement>) => {
    if (inputEvent.key === "Escape") {
      cancelLink();
      return;
    }
    if (inputEvent.key !== "Tab") return;
    const focusable = Array.from(linkDialogRef.current?.querySelectorAll<HTMLElement>("input, button") ?? [])
      .filter((element) => !element.hasAttribute("disabled"));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (inputEvent.shiftKey && document.activeElement === first) {
      inputEvent.preventDefault();
      last.focus();
    } else if (!inputEvent.shiftKey && document.activeElement === last) {
      inputEvent.preventDefault();
      first.focus();
    }
  };

  const pastePlainText = (inputEvent: React.ClipboardEvent<HTMLDivElement>) => {
    inputEvent.preventDefault();
    const text = inputEvent.clipboardData.getData("text/plain");
    const field = diaryRef.current;
    if (!field) return;
    const selection = window.getSelection();
    const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
    if (!range || !field.contains(range.commonAncestorContainer)) {
      field.append(document.createTextNode(text));
      updateField(setDescription, serializeEditor(field));
      return;
    }
    range.deleteContents();
    const node = document.createTextNode(text);
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    selection?.removeAllRanges();
    selection?.addRange(range);
    updateField(setDescription, serializeEditor(field));
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
    <div className="diary-field"><label htmlFor="event-description">Diary</label><div className="markdown-toolbar"><button type="button" className="icon-button" aria-label="Bold selection" title="Bold selection" onMouseDown={(inputEvent) => inputEvent.preventDefault()} onClick={() => wrapSelection("strong")}><Bold aria-hidden="true" size={16} /></button><button type="button" className="icon-button" aria-label="Italic selection" title="Italic selection" onMouseDown={(inputEvent) => inputEvent.preventDefault()} onClick={() => wrapSelection("em")}><Italic aria-hidden="true" size={16} /></button><button type="button" className="icon-button" aria-label="Strikethrough selection" title="Strikethrough selection" onMouseDown={(inputEvent) => inputEvent.preventDefault()} onClick={() => wrapSelection("del")}><Strikethrough aria-hidden="true" size={16} /></button><button ref={linkButtonRef} type="button" className="icon-button" aria-label="Link selection" title="Link selection" onMouseDown={(inputEvent) => inputEvent.preventDefault()} onClick={startLink}><Link aria-hidden="true" size={16} /></button></div>{linkEditorOpen && <div className="link-dialog-backdrop" onMouseDown={(inputEvent) => { if (inputEvent.target === inputEvent.currentTarget) cancelLink(); }}><div ref={linkDialogRef} className="link-dialog" role="dialog" aria-modal="true" aria-labelledby="link-dialog-title" onKeyDown={trapLinkDialogFocus}><h3 id="link-dialog-title">Add link</h3><label>URL<input ref={linkInputRef} aria-label="Link URL" value={linkUrl} onChange={(inputEvent) => setLinkUrl(inputEvent.target.value)} /></label><div className="dialog-actions"><button type="button" className="secondary-button" onClick={cancelLink}>Cancel link</button><button type="button" onClick={applyLink}>Apply link</button></div></div></div>}<div id="event-description" ref={diaryRef} className="diary-editor" aria-label="Diary" role="textbox" aria-multiline="true" contentEditable suppressContentEditableWarning dangerouslySetInnerHTML={{ __html: initialDiaryHtml.current }} onPaste={pastePlainText} onDrop={(inputEvent) => inputEvent.preventDefault()} onInput={() => updateField(setDescription, serializeEditor(diaryRef.current!))} /></div>
    <label>Location<input aria-label="Location" value={location} onChange={(inputEvent) => updateField(setLocation, inputEvent.target.value)} /></label>
    <div className="coordinate-fields"><label>Latitude<input aria-label="Latitude" type="number" min="-90" max="90" step="any" value={latitude} onChange={(inputEvent) => updateField(setLatitude, inputEvent.target.value)} /></label><label>Longitude<input aria-label="Longitude" type="number" min="-180" max="180" step="any" value={longitude} onChange={(inputEvent) => updateField(setLongitude, inputEvent.target.value)} /></label></div>
    <label>Images<input aria-label="Images" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(inputEvent) => { selectFiles(Array.from(inputEvent.target.files ?? [])); inputEvent.target.value = ""; }} /></label>
    <p className="field-hint">{existingMedia.length + files.length} of 5 images selected.</p>
    <div className="image-previews">{existingMedia.map((item) => <SavedMediaPreview key={item.id} media={item} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} onRemove={removeExisting} />)}{files.map((item) => <div key={item.id} className="image-preview"><img src={item.previewUrl} alt={`${item.file.name} thumbnail`} /><button type="button" aria-label={`Remove ${item.file.name}`} onClick={() => removePending(item.id)}>Remove</button></div>)}</div>
    <div className="form-actions"><button type="submit">Save Pawprint</button><button type="button" className="secondary-button" onClick={onCancel}>Cancel</button></div>
    {failed.length > 0 && <button type="button" className="secondary-button" onClick={() => void submit(true)}>Retry image upload</button>}
    {uploadedMedia.length > 0 && <MediaCarousel media={uploadedMedia} fetchMediaObjectUrl={fetchMediaObjectUrl} revokeMediaObjectUrl={revokeMediaObjectUrl} />}
  </form>;
}
