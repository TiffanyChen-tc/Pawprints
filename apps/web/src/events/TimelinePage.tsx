import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";

import { ApiError } from "../api/client";
import { deleteEvent as defaultDelete, getCategories, getEvent as defaultGet, getTimeline, updateEvent as defaultUpdate, type Category, type Event } from "./EventApi";
import EventEntry from "./EventEntry";
import EventForm from "./EventForm";

function localDate(date = new Date()) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function shift(date: string, days: number) {
  const [year, month, day] = date.split("-").map(Number);
  const value = new Date(year, month - 1, day);
  value.setDate(value.getDate() + days);
  return localDate(value);
}

type TimelinePageProps = {
  initialDate?: string;
  today?: string;
  loadTimeline?: (date: string) => Promise<Event[]>;
  loadCategories?: () => Promise<Category[]>;
  removeEvent?: (id: string, etag: string) => Promise<void>;
  loadEvent?: (id: string) => Promise<Event>;
  updateEvent?: typeof defaultUpdate;
};

export default function TimelinePage({ initialDate, today = localDate(), loadTimeline = getTimeline, loadCategories = getCategories, removeEvent = defaultDelete, loadEvent = defaultGet, updateEvent = defaultUpdate }: TimelinePageProps) {
  const [date, setDate] = useState(initialDate ?? today);
  const [events, setEvents] = useState<Event[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formEvent, setFormEvent] = useState<Event | null | undefined>(undefined);
  const [conflict, setConflict] = useState<Event | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void Promise.all([loadTimeline(date), loadCategories()]).then(([next, cats]) => {
      if (!active) return;
      setEvents([...next].sort((left, right) => left.occurred_at.localeCompare(right.occurred_at)));
      setCategories(cats);
    }).catch(() => {
      if (active) setError("Could not load your timeline.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [date, loadCategories, loadTimeline]);

  const reviewLatest = async (event: Event, openForEdit = false) => {
    try {
      const latest = await loadEvent(event.id);
      setConflict(latest);
      setEvents((items) => items.map((item) => item.id === latest.id ? latest : item));
      if (openForEdit) setFormEvent(latest);
    } catch {
      setError("Could not load the latest Pawprint for review.");
    }
  };

  const remove = async (event: Event) => {
    if (!window.confirm(`Delete ${event.title}?`)) return;
    try {
      await removeEvent(event.id, event.etag);
      setEvents((items) => items.filter((item) => item.id !== event.id));
    } catch (reason) {
      if ((reason instanceof ApiError ? reason.status : (reason as { status?: number }).status) === 412) {
        await reviewLatest(event);
      } else {
        setError("Could not delete this Pawprint. Please try again.");
      }
    }
  };

  const saved = (event: Event) => {
    setEvents((items) => {
      const withoutSaved = items.filter((item) => item.id !== event.id);
      return [...withoutSaved, event].sort((left, right) => left.occurred_at.localeCompare(right.occurred_at));
    });
    setFormEvent(undefined);
  };

  return <section className="timeline">
    <div className="timeline-heading"><p className="eyebrow">Private journal</p><h1>Your Pawprints</h1></div>
    <div className="timeline-toolbar">
      <button type="button" className="icon-button" aria-label="Previous day" title="Previous day" onClick={() => setDate(shift(date, -1))}><ChevronLeft aria-hidden="true" /></button>
      <input aria-label="Timeline date" type="date" value={date} onChange={(inputEvent) => setDate(inputEvent.target.value)} />
      <button type="button" className="icon-button" aria-label="Next day" title="Next day" onClick={() => setDate(shift(date, 1))}><ChevronRight aria-hidden="true" /></button>
      <button type="button" className="secondary-button" onClick={() => setDate(today)}>Today</button>
      <button type="button" onClick={() => setFormEvent(null)}><Plus aria-hidden="true" size={16} /> New Pawprint</button>
    </div>
    {formEvent !== undefined && <EventForm key={`${formEvent?.id ?? "new"}-${formEvent?.etag ?? ""}`} categories={categories} event={formEvent ?? undefined} updateEvent={updateEvent} onCategoryCreated={(category) => setCategories((items) => [...items, category])} onConflict={(event) => void reviewLatest(event, true)} onCompleted={() => setFormEvent(undefined)} onSaved={saved} />}
    {loading && <p role="status">Loading timeline...</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {conflict && <p role="alert" className="form-error">This Pawprint changed since you loaded it. Review the latest version: {conflict.title}</p>}
    {!loading && !error && events.length === 0 && <p className="empty-state">No Pawprints for this date yet.</p>}
    <div className="timeline-entries">{events.map((event) => <EventEntry key={event.id} event={event} onEdit={(selected) => setFormEvent(selected)} onDelete={remove} />)}</div>
  </section>;
}
