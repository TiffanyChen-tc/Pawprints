import { useEffect, useState } from "react";
import { ChevronDown, Pencil, Trash2 } from "lucide-react";

import MediaCarousel from "../media/MediaCarousel";
import { getEventMedia, type Media } from "../media/MediaApi";
import type { Event } from "./EventApi";
import MarkdownDescription from "./MarkdownDescription";

export default function EventEntry({ event, onEdit, onDelete, loadMedia = getEventMedia }: { event: Event; onEdit: (event: Event) => void; onDelete: (event: Event) => void; loadMedia?: (eventId: string) => Promise<Media[]> }) {
  const [expanded, setExpanded] = useState(false);
  const [media, setMedia] = useState<Media[] | null>(null);
  const [mediaError, setMediaError] = useState(false);
  const time = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", timeZone: event.timezone }).format(new Date(event.occurred_at));

  const loadPrivateMedia = () => {
    setMediaError(false);
    void loadMedia(event.id).then(setMedia).catch(() => setMediaError(true));
  };

  useEffect(() => {
    if (expanded && media === null && !mediaError) loadPrivateMedia();
  }, [expanded]);

  return <article className="event-entry">
    <button className="entry-summary" type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}><span>{time}</span><strong>{event.title}</strong><span>{event.category_name}</span><ChevronDown aria-hidden="true" size={18} /></button>
    {expanded && <div className="entry-detail">
      {event.mood && <p>Mood: {event.mood}</p>}
      {event.location_name && <p>{event.location_name}</p>}
      {event.description && <MarkdownDescription source={event.description} />}
      {media && <MediaCarousel media={media} />}
      {mediaError && <p className="media-error">Images could not load. <button type="button" className="text-button" onClick={loadPrivateMedia}>Retry images</button></p>}
      <div className="entry-actions"><button type="button" className="secondary-button" onClick={() => onEdit(event)} aria-label={`Edit ${event.title}`}><Pencil aria-hidden="true" size={16} /> Edit</button><button type="button" className="danger" onClick={() => onDelete(event)} aria-label={`Delete ${event.title}`}><Trash2 aria-hidden="true" size={16} /> Delete</button></div>
    </div>}
  </article>;
}
