import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import type { DirectoryPerson } from "./peopleWorkspace";
const columns = ["email", "department", "workspaces", "teams", "batches", "status"];

export function PageSelection({ people, selected, onToggle }: { people: DirectoryPerson[]; selected: number[]; onToggle: () => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const active = people.filter(p => p.status === "active");
  const count = active.filter(p => selected.includes(p.id)).length;
  useEffect(() => { if (ref.current) ref.current.indeterminate = count > 0 && count < active.length; }, [count, active.length]);
  return <label className="inline-flex items-center gap-2"><input ref={ref} type="checkbox" aria-label="Select all on this page" checked={!!active.length && count === active.length} disabled={!active.length} onChange={onToggle} />Select page</label>;
}

export default function DirectoryTable({ people, selected, onSelect, onTogglePage, backTo, sort, onSort, columnsValue, onColumnsChange }: {
  people: DirectoryPerson[]; selected: number[]; onSelect: (person: DirectoryPerson) => void; onTogglePage: () => void;
  backTo: string; sort: string; onSort: (value: string) => void; columnsValue?: string; onColumnsChange?: (value:string)=>void;
}) {
  const user = useAuthStore(s => s.user);
  const storageKey = `pms-directory-columns:${user?.id}:${user?.access?.companyId}`;
  const [visible, setVisible] = useState(columns);
  const direction = (column: string) => sort === column ? "ascending" as const : sort === `${column}_desc` ? "descending" as const : "none" as const;
  const sortButton = (column: string) => <button onClick={() => onSort(sort === column ? `${column}_desc` : column)}>{column} {direction(column) === "ascending" ? "↑" : direction(column) === "descending" ? "↓" : "↕"}</button>;
  useEffect(() => { try { const value = columnsValue !== undefined ? columnsValue.split(",") : JSON.parse(localStorage.getItem(storageKey) || "null"); setVisible(Array.isArray(value) ? columns.filter(c => value.includes(c)) : columns); } catch { setVisible(columns); } }, [storageKey, columnsValue]);
  const toggle = (column: string) => { const next = visible.includes(column) ? visible.filter(c => c !== column) : [...visible, column]; try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Keep session preferences when storage is unavailable. */ } setVisible(next); onColumnsChange?.(next.join(",") || "none"); };
  return <div className="pd-directory-table">
    <details className="mb-2"><summary>Choose columns</summary><div className="flex flex-wrap gap-4 py-3">{columns.map(c => <label key={c} className="capitalize"><input type="checkbox" checked={visible.includes(c)} onChange={() => toggle(c)} /> {c}</label>)}</div></details>
    <div className="max-h-[65vh] overflow-auto rounded-lg border"><table className="w-full text-left text-sm">
      <thead className="sticky top-0 z-10 bg-background"><tr><th className="sticky left-0 bg-background p-3"><PageSelection people={people} selected={selected} onToggle={onTogglePage} /></th>
        <th className="p-3 capitalize" aria-sort={direction("name")}>{sortButton("name")}</th>
        {visible.map(c => <th key={c} className="p-3 capitalize" aria-sort={direction(c)}>{["email", "status"].includes(c) ? sortButton(c) : c}</th>)}
      </tr></thead><tbody>{people.map(person => <tr key={person.id} className="border-t">
        <td className="sticky left-0 bg-background p-3"><input type="checkbox" aria-label={`Select ${person.email}`} disabled={person.status !== "active"} checked={selected.includes(person.id)} onChange={() => onSelect(person)} /></td>
        <td className="p-3"><Link className="font-semibold text-primary" to={`/pms/people/${person.id}?returnTo=${encodeURIComponent(backTo)}`}>{person.name}</Link><small className="block">{person.classification}</small></td>
        {visible.map(c => <td key={c} className="p-3">{c === "status" ? <><span>{person.status === "active" ? "Login enabled" : "Login disabled"}</span>{person.employment_status && <small className="block">{person.classification}: {person.employment_status}</small>}</> : ["teams", "batches", "workspaces"].includes(c) ? (person[c as "teams" | "batches" | "workspaces"] || []).map(p => p.name).join(", ") || "—" : String(person[c as "email" | "department"] || "—")}</td>)}
      </tr>)}</tbody>
    </table></div>
  </div>;
}
