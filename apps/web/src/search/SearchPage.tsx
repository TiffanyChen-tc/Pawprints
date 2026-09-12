import { useEffect, useState } from "react";

import EventEntry from "../events/EventEntry";
import { getCategories, type Category, type Event, type Mood } from "../events/EventApi";
import { searchEvents, type SearchFilters } from "./SearchApi";

type SearchPageProps = {
  loadSearch?: (filters: SearchFilters) => Promise<Event[]>;
  loadCategories?: () => Promise<Category[]>;
};

const moods: Mood[] = ["great", "good", "neutral", "low", "bad"];

export default function SearchPage({ loadSearch = searchEvents, loadCategories = getCategories }: SearchPageProps) {
  const [draft, setDraft] = useState<SearchFilters>({});
  const [filters, setFilters] = useState<SearchFilters>({});
  const [events, setEvents] = useState<Event[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void loadCategories().then((items) => {
      if (active) setCategories(items);
    }).catch(() => {
      if (active) setError("Could not load search filters.");
    });
    return () => { active = false; };
  }, [loadCategories]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void loadSearch(filters).then((items) => {
      if (active) setEvents(items);
    }).catch(() => {
      if (active) setError("Could not search your Pawprints. Please try again.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [filters, loadSearch]);

  const update = (name: keyof SearchFilters, value: string) => {
    setDraft((current) => ({ ...current, [name]: value || undefined }));
  };

  return <section className="search-page">
    <div className="page-heading"><p className="eyebrow">Private journal</p><h1>Search Pawprints</h1></div>
    <form className="filter-panel" onSubmit={(event) => { event.preventDefault(); setFilters(draft); }}>
      <label>Keyword<input aria-label="Keyword" value={draft.keyword ?? ""} onChange={(event) => update("keyword", event.target.value)} /></label>
      <label>From<input aria-label="Start date" type="date" value={draft.start_date ?? ""} onChange={(event) => update("start_date", event.target.value)} /></label>
      <label>To<input aria-label="End date" type="date" value={draft.end_date ?? ""} onChange={(event) => update("end_date", event.target.value)} /></label>
      <label>Category<select aria-label="Category" value={draft.category_id ?? ""} onChange={(event) => update("category_id", event.target.value)}><option value="">All categories</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
      <label>Mood<select aria-label="Mood" value={draft.mood ?? ""} onChange={(event) => update("mood", event.target.value)}><option value="">All moods</option>{moods.map((mood) => <option key={mood} value={mood}>{mood}</option>)}</select></label>
      <label>Location<input aria-label="Location" value={draft.location ?? ""} onChange={(event) => update("location", event.target.value)} /></label>
      <div className="filter-actions"><button type="submit">Apply filters</button><button type="button" className="secondary-button" onClick={() => { setDraft({}); setFilters({}); }}>Clear</button></div>
    </form>
    {loading && <p role="status">Searching Pawprints...</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {!loading && !error && events.length === 0 && <p className="empty-state">No matching Pawprints.</p>}
    <div className="timeline-entries">{events.map((event) => <EventEntry key={event.id} event={event} />)}</div>
  </section>;
}
