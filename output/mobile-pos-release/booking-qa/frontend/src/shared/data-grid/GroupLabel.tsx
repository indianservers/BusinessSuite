import type { CSSProperties } from "react";
import { BadgeDollarSign, CheckCircle2, Circle, CircleDashed, Clock3, Flag, Layers, PauseCircle, PlayCircle, UserRound, XCircle } from "lucide-react";
import "./group-label.css";

/** Shared visual language for both editable tables and remote grids. */
function semanticAppearance(label: string, field = "") {
  const value = label.trim().toLowerCase().replace(/[_-]+/g, " ");
  if (/priority/i.test(field)) return {tone: /critical|high|urgent/.test(value) ? "red" : /medium|normal/.test(value) ? "amber" : "blue", Icon: Flag};
  if (/^(complete[d]?|done|closed|won|paid|approved|success|succeeded|resolved|published|present|healthy)$/.test(value)) return { tone: "green", Icon: CheckCircle2 };
  if (/bill|invoice|collection/.test(value)) return { tone: "pink", Icon: BadgeDollarSign };
  if (/client|customer/.test(value) && /pending|waiting/.test(value)) return { tone: "brown", Icon: UserRound };
  if (/hold|paused|blocked/.test(value)) return { tone: "amber", Icon: PauseCircle };
  if (/cancel|lost|reject|overdue|critical|high|failed|error|absent|terminated|suspended/.test(value)) return { tone: "red", Icon: XCircle };
  if (/^(active|in progress|in process|working|confirmed)$/.test(value)) return { tone: "blue", Icon: PlayCircle };
  if (/pending|waiting|review/.test(value)) return { tone: "amber", Icon: Clock3 };
  if (/^(planned|scheduled)$/.test(value)) return { tone: "purple", Icon: Clock3 };
  if (/^(draft|to do|unassigned|not started|disabled|inactive|not set|hidden)$/.test(value)) return { tone: "gray", Icon: CircleDashed };
  if (/^new$/.test(value)) return { tone: "purple", Icon: Circle };
  let hash = 0;
  for (const char of value) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return { color: `hsl(${(hash % 36000) / 100} 58% 40%)`, tone: ["blue", "purple", "brown", "pink", "green", "amber"][hash % 6], Icon: /owner|assignee|employee|team/i.test(field) ? UserRound : /priority/i.test(field) ? Flag : Layers };
}

/** Stable colors distinguish categories that share the same semantic status. */
export function groupAppearance(label: string, field = "") {
  const appearance = semanticAppearance(label, field);
  let hash = 2166136261;
  for (const char of `${field}:${label.trim()}`) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  return {...appearance, color: `hsl(${hash / 4294967296 * 360} 58% 38%)`};
}

// Allocate colors across the actual categories, avoiding adjacent PINs with near-identical hashes.
const categoryPalette = ["#2866bc", "#bb1762", "#21845b", "#986309", "#7150bf", "#bd4825", "#087c8c", "#9b377b", "#587526", "#65503b", "#39518e", "#876414"];
export function groupCategoryColors(labels: Iterable<string>): Map<string,string> {
  const unique = [...new Set(labels)].sort((a,b)=>a.localeCompare(b));
  return new Map(unique.map((label,index)=>[label, index < categoryPalette.length ? categoryPalette[index] : `hsl(${((index-categoryPalette.length)*137.508+15)%360} ${55+index%3*10}% ${30+index%4*5}%)`]));
}

export default function GroupLabel({ label, field, count, color: categoryColor }: { label: string; field?: string; count: number; color?:string }) {
  const { tone, Icon, color: fallbackColor } = groupAppearance(label, field);
  const color = categoryColor || fallbackColor;
  return <><span className={`suite-group-badge suite-group-${tone}`} style={color ? {"--group-color":color} as CSSProperties : undefined} title={field ? `${field}: ${label}` : label}><Icon size={12} strokeWidth={2.3} aria-hidden="true"/><span>{label.replace(/_/g, " ")}</span></span><span className={`suite-group-count suite-group-${tone}`} style={color ? {"--group-color":color} as CSSProperties : undefined} aria-label={`${count} records`}>{count.toLocaleString()}</span></>;
}

export function RecordStatusIcon({ label, field }: { label: string; field?: string }) {
  const { tone, Icon, color } = groupAppearance(label, field);
  return <span className={`suite-record-status suite-group-${tone}`} style={color ? {"--group-color":color} as CSSProperties : undefined} title={label}><Icon size={15} strokeWidth={2} aria-hidden="true"/><span className="sr-only">{label}</span></span>;
}
