import { Fragment } from "react";
function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g).map((part, index) => {
    if (part.startsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`")) return <code key={index} className="rounded bg-muted px-1">{part.slice(1, -1)}</code>;
    const link = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part);
    return link ? <a key={index} href={link[2]} target="_blank" rel="noopener noreferrer" className="text-primary underline">{link[1]}</a> : part;
  });
}
export default function DocumentPreview({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks = []; let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const code = []; i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++; blocks.push(<pre key={i} className="overflow-x-auto rounded-md bg-muted p-3 text-sm"><code>{code.join("\n")}</code></pre>); continue;
    }
    if (line.trim().startsWith("|") && lines[i + 1]?.match(/^\s*\|?[\s:|-]+\|\s*$/)) {
      const cells = (value: string) => value.trim().replace(/^\||\|$/g, "").split("|").map(value => value.trim());
      const headers = cells(line); i += 2; const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]));
      blocks.push(<div key={i} className="overflow-x-auto"><table className="w-full border-collapse text-left text-sm"><thead><tr>{headers.map((header, index) => <th key={index} className="border bg-muted p-2">{inline(header)}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, index) => <td key={index} className="border p-2">{inline(cell)}</td>)}</tr>)}</tbody></table></div>); continue;
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) blocks.push(<div role="heading" aria-level={heading[1].length} key={i} className={heading[1].length === 1 ? "pt-3 text-2xl font-semibold" : heading[1].length === 2 ? "pt-2 text-xl font-semibold" : "pt-2 text-lg font-semibold"}>{inline(heading[2])}</div>);
    else if (/^- \[[ x]\] /.test(line)) blocks.push(<p key={i} className="flex gap-2"><input aria-label={line.slice(6)} type="checkbox" checked={line[3] === "x"} readOnly />{inline(line.slice(6))}</p>);
    else if (/^[-*] /.test(line)) blocks.push(<p key={i} className="pl-4">• {inline(line.slice(2))}</p>);
    else if (/^\d+\. /.test(line)) blocks.push(<p key={i} className="pl-4">{inline(line)}</p>);
    else if (line.startsWith("> ")) blocks.push(<blockquote key={i} className="border-l-4 pl-3 text-muted-foreground">{inline(line.slice(2))}</blockquote>);
    else blocks.push(<p key={i} className="min-h-3 whitespace-pre-wrap break-words">{inline(line)}</p>);
    i++;
  }
  return <div className="space-y-3">{blocks.map((block, index) => <Fragment key={index}>{block}</Fragment>)}</div>;
}
