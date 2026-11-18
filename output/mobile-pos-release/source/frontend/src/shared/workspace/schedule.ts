/** Calendar-day arithmetic stays stable across daylight-saving and timezone changes. */
export const dayNumber = (value?: string): number | null => {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T|$)/.exec(value || "");
  if (!match) return null;
  const [, year, month, day] = match.map(Number);
  const stamp = Date.UTC(year, month - 1, day);
  const date = new Date(stamp);
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day ? stamp / 86400000 : null;
};
export const todayNumber = () => {
  const now = new Date();
  return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / 86400000;
};
export const formatDay = (day: number, options: Intl.DateTimeFormatOptions = {month:"short", day:"numeric"}) => new Date(day * 86400000).toLocaleDateString(undefined, {...options, timeZone:"UTC"});
export function scheduleRange(records: {start?: string; due?: string}[]) {
  const dates = records.flatMap(record => [dayNumber(record.start), dayNumber(record.due)]).filter((day): day is number => day !== null);
  const start = (dates.length ? Math.min(...dates) : todayNumber()) - 3;
  const end = (dates.length ? Math.max(...dates) : todayNumber()) + 7;
  return {start, days: Math.max(28, end - start + 1)};
}
export function scheduleBar(record: {start?: string; due?: string}, start: number) {
  const first = dayNumber(record.start) ?? dayNumber(record.due);
  const last = dayNumber(record.due) ?? first;
  if (first === null || last === null) return null;
  return {offset: Math.min(first, last) - start, days: Math.abs(last - first) + 1, reversed: last < first};
}
