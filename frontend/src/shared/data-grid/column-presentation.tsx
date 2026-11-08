import { normalizePriority } from "@/shared/priority/priority";
import { Activity, BadgeCheck, CalendarDays, CheckSquare, CircleDot, Columns3, FileText, Hash, Layers, ListChecks, Mail, MoreHorizontal, Package, Phone, Star, Tag, TrendingUp, UserRound, Users, Wallet, type LucideIcon } from "lucide-react";
import { Children, type ReactNode } from "react";

/** Domain labels remain page-owned; these are only decorative heading icons. */
export function columnIcon(title: string): LucideIcon {
  if (/^favou?rites?$/i.test(title)) return Star;
  if (/^(select|selected)$/i.test(title)) return CheckSquare;
  if (/actions?|tools/i.test(title)) return MoreHorizontal;
  if (/progress|completion|utilization|probability/i.test(title)) return TrendingUp;
  if (/\b(date|dates|due|start|end|updated|created|joined|birthday|period)\b|_at$/i.test(title)) return CalendarDays;
  if (/\b(status|stage|state|priority)\b/i.test(title)) return CircleDot;
  if (/approval|verified|compliance/i.test(title)) return BadgeCheck;
  if (/email/i.test(title)) return Mail;
  if (/phone|mobile/i.test(title)) return Phone;
  if (/team|department|members|company|customer|client|vendor|supplier/i.test(title)) return Users;
  if (/owner|assignee|assigned|employee|person|contact|lead|user/i.test(title)) return UserRound;
  if (/amount|price|cost|balance|debit|credit|total|revenue|payment|salary|value|tax/i.test(title)) return Wallet;
  if (/quantity|qty|number|count|score|hours|days|^id$|code|reference/i.test(title)) return Hash;
  if (/product|item|sku|stock|warehouse/i.test(title)) return Package;
  if (/tag|label|category|type/i.test(title)) return Tag;
  if (/group|workspace|project/i.test(title)) return Layers;
  if (/task|checklist/i.test(title)) return ListChecks;
  if (/activity|event/i.test(title)) return Activity;
  if (/file|document|invoice|order|contract|name|title|subject/i.test(title)) return FileText;
  return Columns3;
}

export function ColumnHeadingIcon({ title }: { title: string }) {
  const Icon = columnIcon(title);
  return <Icon size={13} aria-hidden="true" className="suite-column-icon" />;
}

/** Upgrade explicit percentages only. Existing editors and domain renderers stay intact. */
export function columnValue(title: string, content: ReactNode): ReactNode {
  if (/\bpriority\b/i.test(title.trim()) && (typeof content === "string" || typeof content === "number")) {
    const priority=normalizePriority(content);
    return priority ? <span data-priority-badge data-priority={priority}>{content}</span> : content;
  }
  if (!/\b(progress|completion)\b/i.test(title)) return content;
  const parts = Children.toArray(content);
  if (!parts.length || !parts.every(part => typeof part === "string" || typeof part === "number")) return content;
  const text = parts.join("").trim();
  if (!/^\d+(?:\.\d+)?%$/.test(text)) return content;
  const value = Number(text.slice(0, -1));
  if (value < 0 || value > 100) return content;
  return <span className="suite-column-progress"><span role="progressbar" aria-label={title} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${value}%`}}/></span><span>{text}</span></span>;
}
