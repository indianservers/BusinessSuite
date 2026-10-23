import { useRef, useState } from "react";
import type { TaskPriority } from "../types";

const choices: { value: TaskPriority; color: string; shortcut: string }[] = [
  { value: "Urgent", color: "text-red-600", shortcut: "1" },
  { value: "High", color: "text-amber-600", shortcut: "2" },
  { value: "Medium", color: "text-blue-600", shortcut: "3" },
  { value: "Low", color: "text-slate-500", shortcut: "4" },
];

export default function PriorityPicker({ value, disabled, onChange }: {
  value: TaskPriority; disabled: boolean; onChange: (priority: TaskPriority) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const root = useRef<HTMLDetailsElement>(null);
  async function choose(priority: TaskPriority) {
    if (disabled) return;
    await onChange(priority);
    if (root.current) root.current.open = false;
    setSearch("");
  }
  return <details ref={root} className="relative" onKeyDown={event => {
    if (event.key === "Escape" && root.current) { root.current.open = false; root.current.querySelector("summary")?.focus(); }
    if (root.current?.open && event.altKey) {
      const choice = choices.find(choice => choice.shortcut === event.key);
      if (choice) { event.preventDefault(); void choose(choice.value); }
    }
  }}>
    <summary aria-label="Task priority" className="cursor-pointer rounded-md border p-2">{value === "Medium" ? "Normal (Medium)" : value}</summary>
    <div className="absolute right-0 z-30 mt-1 w-64 max-w-[80vw] space-y-2 rounded-lg border bg-background p-3 shadow-lg">
      <input aria-label="Search priorities" placeholder="Search priorities" value={search} onChange={event => setSearch(event.target.value)} className="w-full rounded border bg-background p-2 text-sm" />
      {choices.filter(choice => `${choice.value} ${choice.value === "Medium" ? "Normal" : ""}`.toLowerCase().includes(search.toLowerCase())).map(choice => <button key={choice.value} type="button" disabled={disabled} aria-pressed={value === choice.value} className="flex w-full items-center justify-between rounded p-2 text-left text-sm hover:bg-muted disabled:opacity-50" onClick={() => void choose(choice.value)}><span className={choice.color}>⚑ {choice.value === "Medium" ? "Normal (Medium)" : choice.value}</span><kbd className="text-xs text-muted-foreground">Alt+{choice.shortcut}</kbd></button>)}
      {!choices.some(choice => `${choice.value} ${choice.value === "Medium" ? "Normal" : ""}`.toLowerCase().includes(search.toLowerCase())) && <p className="text-sm text-muted-foreground">No matching priority.</p>}
    </div>
  </details>;
}
