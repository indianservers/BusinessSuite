import type { Lead, ListResult } from "./api";

/** Apply only a known row transition; filtered summaries require a server read. */
export function updateLeadSummary(current: ListResult, lead: Lead, created: boolean) {
  const previous = current.items.find(row => row.id === lead.id);
  if ((!previous && !created) || !lead.signals) return current;
  const summary = {...current.summary};
  summary.total = Math.max(0, summary.total + (previous ? 0 : 1));
  for (const key of ["active", "overdue", "slaBreached", "stale"] as const) {
    summary[key] = Math.max(0, summary[key] + Number(lead.signals[key]) - Number(previous?.signals?.[key] || false));
  }
  const adjust = (counts: Record<string, number>, oldKey: string | undefined, newKey: string) => {
    const next = {...counts};
    if (oldKey) next[oldKey] = Math.max(0, (next[oldKey] || 0) - 1);
    next[newKey] = (next[newKey] || 0) + 1;
    return next;
  };
  return {...current, summary,
    byStage: adjust(current.byStage, previous?.status, lead.status),
    bySource: adjust(current.bySource, previous ? previous.source || "Other" : undefined, lead.source || "Other"),
  };
}
