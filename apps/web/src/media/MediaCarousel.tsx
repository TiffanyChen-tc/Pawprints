import { useEffect, useState } from "react";

import { fetchMediaObjectUrl as defaultFetch, revokeMediaObjectUrl as defaultRevoke, type Media } from "./MediaApi";

export default function MediaCarousel({ media, fetchMediaObjectUrl = defaultFetch, revokeMediaObjectUrl = defaultRevoke }: { media: Media[]; fetchMediaObjectUrl?: (id: string) => Promise<string>; revokeMediaObjectUrl?: (url: string) => void }) {
  const [urlState, setUrlState] = useState<{ media: Media[]; urls: string[] }>({ media, urls: [] });
  const urls = urlState.media === media ? urlState.urls : [];
  const [activeImage, setActiveImage] = useState<{ media: Media[]; url: string } | null>(null);
  const activeUrl = activeImage?.media === media ? activeImage.url : null;

  useEffect(() => {
    let active = true;
    let failed = false;
    let created: string[] = [];
    setActiveImage(null);
    Promise.all(media.map(async (item) => {
      const url = await fetchMediaObjectUrl(item.id);
      if (!active || failed) {
        revokeMediaObjectUrl(url);
        return url;
      }
      created = [...created, url];
      return url;
    })).then((next) => {
      if (active && !failed) setUrlState({ media, urls: next });
    }).catch(() => {
      failed = true;
      created.forEach((url) => revokeMediaObjectUrl(url));
      created = [];
    });
    return () => {
      active = false;
      created.forEach((url) => revokeMediaObjectUrl(url));
    };
  }, [media, fetchMediaObjectUrl, revokeMediaObjectUrl]);

  useEffect(() => { if (!activeUrl) return; const close = (event: KeyboardEvent) => { if (event.key === "Escape") setActiveImage(null); }; document.addEventListener("keydown", close); return () => document.removeEventListener("keydown", close); }, [activeUrl]);

  if (!media.length) return null;
  return <><div className="media-carousel">{urls.map((url, index) => <button key={media[index]?.id} type="button" aria-label={`Open image ${index + 1}`} onClick={(click) => { click.stopPropagation(); setActiveImage({ media, url }); }}><img src={url} alt={`Pawprint image ${index + 1}`} /></button>)}</div>{activeUrl && <div className="media-lightbox" role="dialog" aria-modal="true" aria-label="Image viewer" onClick={() => setActiveImage(null)}><div className="media-lightbox-content" onClick={(click) => click.stopPropagation()}><button type="button" aria-label="Close image viewer" onClick={() => setActiveImage(null)}>Close</button><img src={activeUrl} alt="Enlarged Pawprint image" /></div></div>}</>;
}
