export type CalendarSection = {
  id: string;
  title: string;
  enabled: boolean;
  filter:
    | "priorities"
    | "people"
    | "assigned"
    | "overdue"
    | "backlog"
    | "high_priority";
};
export type CalendarPrefs = {
  grid_size: "default" | "large" | "xl";
  event_style: "subtle" | "solid";
  duration: 15 | 30 | 45 | 60 | 90 | 120;
  color_by: "project" | "status" | "priority";
  week_start: number;
  timezone: string;
  weekends: boolean;
  week_numbers: boolean;
  show_event_details: boolean;
  show_time_left: boolean;
  browser_reminders: boolean;
  quick_join: 1 | 2 | 5 | 10 | 15;
  show_task_dates: boolean;
  task_scope: "all" | "mine";
  closed_tasks: boolean;
  recurring: boolean;
  default_project: number | null;
  prefix: string;
  focus_visibility: "private" | "workspace";
  workdays: { day: number; enabled: boolean; start: string; end: string }[];
  sections: CalendarSection[];
  notes_name: string;
  notes_template: string;
};
export const calendarDefaults: CalendarPrefs = {
  grid_size: "default",
  event_style: "subtle",
  duration: 60,
  color_by: "project",
  week_start: 0,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  weekends: true,
  week_numbers: false,
  show_event_details: true,
  show_time_left: true,
  browser_reminders: false,
  quick_join: 2,
  show_task_dates: true,
  task_scope: "all",
  closed_tasks: true,
  recurring: false,
  default_project: null,
  prefix: "Work on",
  focus_visibility: "private",
  workdays: Array.from({ length: 7 }, (_, day) => ({
    day,
    enabled: day < 5,
    start: "09:00",
    end: "17:00",
  })),
  sections: [
    {
      id: "priorities",
      title: "Priorities",
      enabled: true,
      filter: "priorities",
    },
    { id: "people", title: "People", enabled: true, filter: "people" },
    {
      id: "assigned",
      title: "Assigned to me",
      enabled: true,
      filter: "assigned",
    },
    {
      id: "overdue",
      title: "Today & overdue",
      enabled: true,
      filter: "overdue",
    },
    { id: "backlog", title: "Backlog", enabled: true, filter: "backlog" },
  ],
  notes_name: "Meeting notes",
  notes_template: "Agenda\n\nDecisions\n\nAction items",
};
export type CalendarEvent = {
  id: number;
  owner_id: number;
  workspace_id: number | null;
  task_id: number | null;
  title: string;
  description: string;
  start_at: string;
  end_at: string;
  timezone: string;
  kind: "meeting" | "focus";
  visibility: "private" | "workspace";
  meeting_url: string;
  revision: number;
  can_edit: boolean;
};
export function zonedDay(value: string, zone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  return ["year", "month", "day"]
    .map((t) => parts.find((p) => p.type === t)?.value)
    .join("-");
}
export function zonedInput(value: string, zone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(value));
  const v = (t: string) => parts.find((p) => p.type === t)?.value;
  return `${v("year")}-${v("month")}-${v("day")}T${v("hour")}:${v("minute")}`;
}
export function localToUTC(value: string, zone: string) {
  const guess = Date.parse(value + "Z");
  if (!Number.isFinite(guess)) throw Error("Choose a valid date and time");
  let current = guess;
  for (let i = 0; i < 3; i++) {
    const display = Date.parse(
      zonedInput(new Date(current).toISOString(), zone) + "Z",
    );
    current += guess - display;
  }
  if (zonedInput(new Date(current).toISOString(), zone) !== value)
    throw Error(
      "This local time does not exist due to a daylight-saving change. Choose another time.",
    );
  return new Date(current).toISOString();
}
export function saveCalendarFile(content: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function calendarICS(
  events: CalendarEvent[],
  tasks: { id: number | string; title: string; due_date: string | null }[],
) {
  const esc = (s: string) =>
    s
      .replace(/\\/g, "\\\\")
      .replace(/\r?\n/g, "\\n")
      .replace(/;/g, "\\;")
      .replace(/,/g, "\\,");
  const stamp = (s: string) =>
    new Date(s)
      .toISOString()
      .replace(/[-:]/g, "")
      .replace(/\.\d{3}/, "");
  const rows = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//BusinessSuite//KaryaFlow//EN",
    "CALSCALE:GREGORIAN",
  ];
  for (const e of new Map(events.map((e) => [e.id, e])).values())
    rows.push(
      "BEGIN:VEVENT",
      `UID:event-${e.id}@karyaflow`,
      `DTSTAMP:${stamp(new Date().toISOString())}`,
      `DTSTART:${stamp(e.start_at)}`,
      `DTEND:${stamp(e.end_at)}`,
      `SUMMARY:${esc(e.title)}`,
      `DESCRIPTION:${esc(e.description)}`,
      `CLASS:${e.visibility === "private" ? "PRIVATE" : "PUBLIC"}`,
      "END:VEVENT",
    );
  for (const t of tasks)
    if (t.due_date)
      rows.push(
        "BEGIN:VEVENT",
        `UID:task-${t.id}@karyaflow`,
        `DTSTAMP:${stamp(new Date().toISOString())}`,
        `DTSTART;VALUE=DATE:${t.due_date.replace(/-/g, "")}`,
        `SUMMARY:${esc(t.title)}`,
        "END:VEVENT",
      );
  rows.push("END:VCALENDAR");
  return (
    rows
      .map((line) => {
        const parts: string[] = [];
        let current = "",
          bytes = 0;
        for (const char of line) {
          const size = new TextEncoder().encode(char).length;
          if (bytes + size > 73) {
            parts.push(current);
            current = " " + char;
            bytes = 1 + size;
          } else {
            current += char;
            bytes += size;
          }
        }
        parts.push(current);
        return parts.join("\r\n");
      })
      .join("\r\n") + "\r\n"
  );
}
