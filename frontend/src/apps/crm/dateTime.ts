// Backend CRM timestamps without an offset are stored as UTC.
// Keep date-only values in their existing calendar-date interpretation.
export function crmTimestamp(value: string | Date): Date {
  if (value instanceof Date) return new Date(value.getTime());
  const utc = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(value);
  return new Date(utc ? `${value.replace(" ", "T")}Z` : value);
}
