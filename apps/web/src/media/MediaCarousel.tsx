import { useEffect, useState } from "react";

import { fetchMediaObjectUrl as defaultFetch, revokeMediaObjectUrl as defaultRevoke, type Media } from "./MediaApi";

export default function MediaCarousel({ media, fetchMediaObjectUrl = defaultFetch, revokeMediaObjectUrl = defaultRevoke }: { media: Media[]; fetchMediaObjectUrl?: (id: string) => Promise<string>; revokeMediaObjectUrl?: (url: string) => void }) {
  const [urls, setUrls] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    let failed = false;
    let created: string[] = [];
    Promise.all(media.map(async (item) => {
      const url = await fetchMediaObjectUrl(item.id);
      if (!active || failed) {
        revokeMediaObjectUrl(url);
        return url;
      }
      created = [...created, url];
      return url;
    })).then((next) => {
      if (active && !failed) setUrls(next);
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

  if (!media.length) return null;
  return <div className="media-carousel">{urls.map((url, index) => <img key={media[index]?.id} src={url} alt={`Pawprint image ${index + 1}`} />)}</div>;
}
