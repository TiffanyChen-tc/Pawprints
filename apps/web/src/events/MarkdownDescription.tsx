import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
export default function MarkdownDescription({ source }: { source: string }) { return <div data-testid="markdown-description"><ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} skipHtml allowedElements={["p", "strong", "em", "del", "ul", "ol", "li", "br"]}>{source}</ReactMarkdown></div>; }
