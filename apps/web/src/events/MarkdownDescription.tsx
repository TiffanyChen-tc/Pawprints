import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

function safeLinkUrl(value: string | undefined) {
  if (!value) return null;
  const trimmed = value.trim();
  try {
    const url = new URL(trimmed);
    return url.protocol === "http:" || url.protocol === "https:" ? trimmed : null;
  } catch {
    return null;
  }
}

export default function MarkdownDescription({ source }: { source: string }) {
  return <div data-testid="markdown-description">
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      skipHtml
      allowedElements={["p", "strong", "em", "del", "ul", "ol", "li", "br", "a"]}
      unwrapDisallowed
      components={{
        a: ({ href, children }) => {
          const safe = safeLinkUrl(href);
          return safe ? <a href={safe} target="_blank" rel="noopener noreferrer">{children}</a> : <>{children}</>;
        },
      }}
    >
      {source}
    </ReactMarkdown>
  </div>;
}
