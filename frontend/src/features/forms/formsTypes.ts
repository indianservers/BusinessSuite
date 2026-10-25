export type Kind =
  | "text"
  | "textarea"
  | "email"
  | "phone"
  | "url"
  | "number"
  | "date"
  | "select"
  | "radio"
  | "multiselect"
  | "checkbox"
  | "rating"
  | "section"
  | "page"
  | "file";
export type Question = {
  global_field_id?: number;
  id: string;
  type: Kind;
  label: string;
  help: string;
  placeholder: string;
  required: boolean;
  width?: "auto" | "full";
  options: string[];
  min: number | null;
  max: number | null;
  condition: {
    field: string;
    operator: "equals" | "not_equals" | "contains" | "not_empty";
    value: string;
  } | null;
};
export type FormSettings = {
  public: boolean;
  captcha: "builtin" | "turnstile";
  max_responses: number | null;
  closes_at: string | null;
  layout: "stacked" | "pages";
  font: "system" | "serif" | "monospace";
  button_radius: number;
  columns?: 1 | 2 | 3;
  intro_enabled?: boolean;
  intro_badge?: string;
  intro_title?: string;
  intro_text?: string;
  surface?: "minimal" | "soft" | "gradient";
};
export const defaultSettings: FormSettings = {
  public: false,
  captcha: "builtin",
  max_responses: null,
  closes_at: null,
  layout: "stacked",
  font: "system",
  button_radius: 10,
};
export type Definition = {
  settings?: FormSettings;
  name: string;
  description: string;
  accent: string;
  submit_label: string;
  success_message: string;
  fields: Question[];
  workflow: {
    enabled: boolean;
    project_id: number | null;
    title_field: string;
    priority: string;
    assignee_id: number | null;
    due_days: number | null;
  };
};
export type Saved = {
  slug?: string;
  module_key?: string;
  legacy_entry_id?: number;
  id: number;
  revision: number;
  version: number;
  open: boolean;
  responses: number;
  draft?: Definition;
  published?: Definition;
  definition?: Definition;
};
export type Answer = string | string[] | boolean | number;
export type Reply = {
  id: number;
  status?: string;
  user_id: number;
  task_id: number | null;
  submitted_at: string;
  version: number;
  answers: Record<string, Answer>;
  labels: Record<string, string>;
};
export const kinds: [Kind, string, string][] = [
  ["text", "Short text", "T"],
  ["textarea", "Long text", "¶"],
  ["email", "Email", "@"],
  ["phone", "Phone", "☎"],
  ["url", "Website", "↗"],
  ["number", "Number", "#"],
  ["date", "Date", "▦"],
  ["select", "Dropdown", "▾"],
  ["radio", "Single choice", "◉"],
  ["multiselect", "Multiple choice", "☷"],
  ["checkbox", "Consent", "☑"],
  ["rating", "Rating", "☆"],
  ["section", "Section", "≡"],
  ["page", "Page break", "▤"],
  ["file", "File upload", "↥"],
];
export const question = (type: Kind, label?: string): Question => ({
  id: "q_" + crypto.randomUUID().replace(/-/g, ""),
  type,
  label: label || kinds.find((k) => k[0] === type)![1],
  help: "",
  placeholder: "",
  required: false,
  options: ["Option 1", "Option 2"],
  min: null,
  max: null,
  condition: null,
});
export function fresh(): Definition {
  const title = question("text", "Request title");
  title.required = true;
  return {
    settings: { ...defaultSettings },
    name: "Untitled form",
    description: "Tell us what you need. We’ll take it from here.",
    accent: "#7c3aed",
    submit_label: "Send request",
    success_message: "Thank you. Your response has been saved.",
    fields: [
      title,
      question("textarea", "Details"),
      question("email", "Contact email"),
    ],
    workflow: {
      enabled: false,
      project_id: null,
      title_field: title.id,
      priority: "Medium",
      assignee_id: null,
      due_days: null,
    },
  };
}
export function visible(f: Question, a: Record<string, Answer>) {
  const c = f.condition;
  if (!c) return true;
  const raw = a[c.field];
  const v = typeof raw === "string" ? raw.trim() : raw;
  if (c.operator === "not_empty")
    return (
      v != null &&
      v !== "" &&
      v !== false &&
      (!Array.isArray(v) || v.length > 0)
    );
  if (c.operator === "contains")
    return typeof v === "string" || Array.isArray(v)
      ? v.includes(c.value)
      : false;
  const same =
    typeof v === "number"
      ? c.value.trim() !== "" && Number(c.value) === v
      : String(v ?? "").toLowerCase() === c.value.toLowerCase();
  return c.operator === "equals" ? same : !same;
}
export function displayed(fields: Question[], answers: Record<string, Answer>) {
  const clean: Record<string, Answer> = {};
  return fields.filter((f) => {
    if (!visible(f, clean)) return false;
    if (f.type !== "section" && answers[f.id] !== undefined)
      clean[f.id] = answers[f.id];
    return true;
  });
}
export function download(data: BlobPart, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
