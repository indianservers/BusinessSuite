// Backend CRM timestamps without an offset are stored as UTC.
// Keep date-only values in their existing calendar-date interpretation.
export function crmTimestamp(value: string | Date): Date {
  if (value instanceof Date) return new Date(value.getTime());
  const utc = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(value);
  return new Date(utc ? `${value.replace(" ", "T")}Z` : value);
}

export function crmLocalDateTime(value: string): string {
  if (!value) return "";
  const date = crmTimestamp(value);
  if (!Number.isFinite(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function crmTaskDate(value?: string): string {
  return !value ? "" : /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : crmLocalDateTime(value).slice(0, 10);
}

export function crmTaskDueValue(date: string, current?: string): string | null {
  if (!date) return null;
  if (current && crmTaskDate(current) === date) return current;
  const time = current?.includes("T") ? crmLocalDateTime(current).slice(11) : "";
  return time ? new Date(`${date}T${time}`).toISOString() : `${date}T12:00:00Z`;
}
