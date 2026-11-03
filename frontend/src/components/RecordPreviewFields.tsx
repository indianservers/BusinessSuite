import type { ReactNode } from "react";
export const label = (key: string) => key.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]/g, " ").replace(/^./, c => c.toUpperCase());
export const privateField = /password|secret|token|credential|authorization|api[_-]?key/i;
export function Fields({ value }: { value: unknown }): ReactNode {
  if (value == null || value === "") return <span className="text-muted-foreground">—</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value !== "object") return <span className="whitespace-pre-wrap break-words">{String(value)}</span>;
  if (Array.isArray(value)) return value.length ? <div className="space-y-3">{value.map((item, i) => <div key={i} className="rounded-md border p-3"><Fields value={item} /></div>)}</div> : <span className="text-muted-foreground">None</span>;
  return <dl className="divide-y">{Object.entries(value).filter(([key]) => !privateField.test(key)).map(([key, item]) => <div key={key} className="grid gap-1 py-3 sm:grid-cols-[minmax(120px,1fr)_minmax(0,2fr)] sm:gap-4"><dt className="min-w-0 break-words text-sm font-medium text-muted-foreground">{label(key)}</dt><dd className="min-w-0 text-sm"><Fields value={item} /></dd></div>)}</dl>;
}
