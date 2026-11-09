export type CollectionField<T> = { id: string; title: string; value: (row: T) => unknown };
export type ScheduleRecord<T> = { row: T; title: string; start: number; end: number; progress?: number };
export const DAY = 86400000;
/** Calendar days only: never guess an ambiguous locale or use creation timestamps as planned dates. */
export function calendarDay(value: unknown): number | undefined {
  if (typeof value !== "string") return;
  const text = value.trim();
  if (text.includes("T") && !Number.isFinite(Date.parse(text))) return;
  let year: number, month: number, day: number;
  let match = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/.exec(text);
  if (match) [, year, month, day] = match.map(Number);
  else {
    match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(text);
    if (!match) return;
    day = Number(match[1]); month = Number(match[2]); year = Number(match[3]);
  }
  const time = Date.UTC(year, month - 1, day), date = new Date(time);
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day ? time : undefined;
}
export function percentage(value: unknown): number | undefined {
  if (typeof value !== "number" && typeof value !== "string") return;
  if (typeof value === "string" && !/^\s*\d+(?:\.\d+)?%?\s*$/.test(value)) return;
  const number = Number(String(value).replace("%", "").trim());
  return Number.isFinite(number) && number >= 0 && number <= 100 ? number : undefined;
}
export function scheduleRecords<T>(rows: T[], fields: CollectionField<T>[]): ScheduleRecord<T>[] {
  const pairs = [
    ["Start date","Due date"], ["Start date","End date"], ["Start date","Expected end date"],
    ["Expected start date","Expected end date"], ["Planned start date","Planned end date"],
    ["Assigned date","Returned date"], ["Resignation date","Last working date"],
    ["From date","To date"], ["Period start","Period end"], ["Valid from","Valid until"],
    ["Start","Due"], ["Start","End"], ["Start time","End time"], ["From","To"], ["Calculated start","Calculated due"],
  ];
  const availablePairs = pairs.flatMap(([from,to]) => {
    const start=fields.find(field=>field.title.toLowerCase()===from.toLowerCase());
    const end=fields.find(field=>field.title.toLowerCase()===to.toLowerCase());
    return start&&end?[{start,end}]:[];
  });
  const identity = fields.find(f => /^(name|title|subject|task|project|employee|contract|order|invoice|course|record|asset)( name| number)?$/i.test(f.title)) || fields.find(f => !/^(select|actions?|status|stage|id|progress)$/i.test(f.title));
  const progress = fields.find(f => /^(progress|completion|completion percent|progress percent)$/i.test(f.title));
  return rows.flatMap(row => {
    for (const {start,end} of availablePairs) {
      const from=calendarDay(start.value(row)),to=calendarDay(end.value(row));
      if(from===undefined||to===undefined||to<from) continue;
      return [{row,title:String(identity?.value(row)||"Record"),start:from,end:to,progress:progress?percentage(progress.value(row)):undefined}];
    }
    return [];
  });
}
export function statusCounts<T>(rows: T[], fields: CollectionField<T>[]): { title: string; count: number }[] {
  const field = fields.find(f => /^(status|stage|state|approval status|billing status|employment status)$/i.test(f.title));
  if (!field) return [];
  const counts = new Map<string, number>();
  for (const row of rows) {
    const raw = field.value(row);
    const value = typeof raw === "string" || typeof raw === "number" ? String(raw).trim() : "";
    const title = !value || /^[—–-]$/.test(value) ? "Not set" : value;
    counts.set(title, (counts.get(title) || 0) + 1);
  }
  const sorted = [...counts].sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]));
  const shown = sorted.slice(0, 5).map(([title,count]) => ({title,count}));
  if (sorted.length > 5) shown.push({title:"Other statuses",count:sorted.slice(5).reduce((sum,[,count])=>sum+count,0)});
  return shown;
}
