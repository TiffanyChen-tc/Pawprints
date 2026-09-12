import { useEffect, useState } from "react";

import { getCategories, type Category } from "../events/EventApi";
import { getActivityCounts, type ActivityCounts, type AnalyticsGrouping, type AnalyticsQuery, type CategoryCount } from "./AnalyticsApi";

export type AnalyticsPreset = "current-month" | "last-30-days";

function dateText(value: Date) {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

export function resolveAnalyticsPreset(preset: AnalyticsPreset, today = new Date()) {
  if (preset === "last-30-days") {
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29);
    return { start_date: dateText(start), end_date: dateText(today) };
  }
  const start = new Date(today.getFullYear(), today.getMonth(), 1);
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  return { start_date: dateText(start), end_date: dateText(end) };
}

type AnalyticsPageProps = {
  today?: Date;
  loadCounts?: (query: AnalyticsQuery) => Promise<ActivityCounts>;
  loadCategories?: () => Promise<Category[]>;
};

function CountRows({ items }: { items: CategoryCount[] }) {
  const maximum = Math.max(0, ...items.map((item) => item.count));
  return <div className="count-rows">{items.map((item) => <div className="count-row" key={item.category_id}><span>{item.category_name}</span><div className="count-track"><span className="count-bar" style={{ width: `${maximum ? (item.count / maximum) * 100 : 0}%` }} /></div><strong>{item.count}</strong></div>)}</div>;
}

export default function AnalyticsPage({ today = new Date(), loadCounts = getActivityCounts, loadCategories = getCategories }: AnalyticsPageProps) {
  const [preset, setPreset] = useState<AnalyticsPreset>("current-month");
  const [grouping, setGrouping] = useState<AnalyticsGrouping>("none");
  const [categoryId, setCategoryId] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [result, setResult] = useState<ActivityCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const range = resolveAnalyticsPreset(preset, today);

  useEffect(() => {
    let active = true;
    void loadCategories().then((items) => {
      if (active) setCategories(items);
    }).catch(() => {
      if (active) setError("Could not load analytics filters. Please try again.");
    });
    return () => { active = false; };
  }, [loadCategories]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const query: AnalyticsQuery = { ...range, grouping, ...(categoryId ? { category_id: categoryId } : {}) };
    void loadCounts(query).then((counts) => {
      if (active) setResult(counts);
    }).catch(() => {
      if (active) setError("Could not load your activity summary. Please try again.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [categoryId, grouping, loadCounts, range.end_date, range.start_date]);

  const empty = result?.grouping === "none" ? result.items.length === 0 : result?.buckets.length === 0;
  return <section className="analytics-page">
    <div className="page-heading"><p className="eyebrow">Private journal</p><h1>Activity summary</h1></div>
    <div className="analytics-controls">
      <label>Range<select aria-label="Range" value={preset} onChange={(event) => setPreset(event.target.value as AnalyticsPreset)}><option value="current-month">Current month</option><option value="last-30-days">Last 30 days</option></select></label>
      <label>Grouping<select aria-label="Grouping" value={grouping} onChange={(event) => setGrouping(event.target.value as AnalyticsGrouping)}><option value="none">Category totals</option><option value="week">Weekly</option><option value="month">Monthly</option></select></label>
      <label>Category<select aria-label="Category" value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">All categories</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
    </div>
    <p className="analytics-range">{range.start_date} to {range.end_date}</p>
    {loading && <p role="status">Loading activity summary...</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {!loading && !error && empty && <p className="empty-state">No Pawprints in this range.</p>}
    {!loading && !error && result?.grouping === "none" && result.items.length > 0 && <CountRows items={result.items} />}
    {!loading && !error && result && result.grouping !== "none" && <div className="analytics-buckets">{result.buckets.map((bucket) => <section className="analytics-bucket" key={bucket.bucket_start_date}><h2>{result.grouping === "week" ? "Week of" : "Month of"} {bucket.bucket_start_date}</h2><CountRows items={bucket.items} /></section>)}</div>}
  </section>;
}
