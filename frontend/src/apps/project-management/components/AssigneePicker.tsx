import { useState } from "react";
import "./assignee-picker.css";

type Person = { id: number; email: string; name?: string };
export default function AssigneePicker({ people, value, onChange, disabled = false, label = "Task assignees" }: {
  people: Person[]; value: number[]; onChange: (ids: number[]) => void | Promise<unknown>; disabled?: boolean; label?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const names = value.map(id => people.find(p => p.id === id)?.email || `Member ${id}`);
  async function change(ids: number[]) {
    setBusy(true);
    try { await onChange(ids); } finally { setBusy(false); }
  }
  return <details className="pms-assignee-picker"><summary aria-label={label}>{names.length ? names.join(", ") : "Unassigned"}</summary>
    <fieldset disabled={disabled || busy} aria-label={label}>
      <legend>{disabled ? "Assigned collaborators" : "Select one or more members"}</legend>
      <input aria-label="Search assignees" placeholder="Find a member…" value={search} onChange={e => setSearch(e.target.value)} />
      {people.filter(p => `${p.email} ${p.name || ""}`.toLowerCase().includes(search.toLowerCase())).map(p => <label key={p.id}><input type="checkbox" checked={value.includes(p.id)} onChange={e => { void change(e.target.checked ? [...value, p.id] : value.filter(id => id !== p.id)); }} />{p.email}</label>)}
      {!people.length && <p>No collaborators available. Invite members to this workspace first.</p>}
      {!!value.length && !disabled && <button type="button" onClick={() => { void change([]); }}>Clear assignees</button>}
      {busy && <p role="status">Saving assignees…</p>}
    </fieldset>
  </details>;
}
