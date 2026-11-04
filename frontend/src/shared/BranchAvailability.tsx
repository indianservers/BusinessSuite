import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { NativeSelect } from "@/components/ui/native-select";

export type BranchAvailabilityValue = { scope: "current" | "selected" | "all"; branch_ids: number[] };
type Branch = { id: number; name: string; can_write: boolean; is_active: boolean };
export default function BranchAvailability({ value, onChange, editing = false, resource, disabled = false }: {
  value?: BranchAvailabilityValue | null; onChange: (value: BranchAvailabilityValue) => void;
  editing?: boolean; resource?: { table: string; id: number; source?: string }; disabled?: boolean;
}) {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [canAll, setCanAll] = useState(false);
  const [current, setCurrent] = useState<number>();
  const [stored, setStored] = useState<BranchAvailabilityValue | null>();
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let active = true;
    setReady(false); setError(""); setStored(undefined);
    Promise.all([api.get("/branches/context", { progress: false }), resource ? api.get("/branches/records/availability", { params: { table_name: resource.table, record_id: resource.id, source: resource.source ?? "crm" }, progress: false }) : Promise.resolve(null)]).then(([context, existing]) => {
      if (!active) return;
      setCanAll(context.data.can_write_all_branches === true);
      setBranches(context.data.branches.filter((b: Branch) => b.is_active));
      setCurrent(context.data.selected ?? context.data.default_branch_id);
      setStored(existing?.data); setReady(true);
    }).catch(() => { if (active) setError("Could not load branch availability. Reopen the form to retry."); });
    return () => { active = false; };
  }, [resource?.table, resource?.id, resource?.source]);
  const choice = value ?? stored;
  const scope = choice?.scope ?? (editing ? "keep" : "current");
  const writable = branches.filter(b => b.can_write);
  return <fieldset className="grid gap-2 rounded border p-3" disabled={disabled || !ready}>
    <legend className="text-sm font-medium">Branch availability</legend>
    <label className="grid gap-1 text-sm">Available in<NativeSelect aria-label="Branch availability" value={scope} onChange={e => {
      const next = e.target.value as BranchAvailabilityValue["scope"];
      onChange({ scope: next, branch_ids: next === "selected" ? [...new Set([...(choice?.branch_ids ?? []), ...(current ? [current] : [])])] : [] });
    }}>{scope === "keep" && <option value="keep">Keep existing availability</option>}<option value="current">This branch{current ? ` — ${branches.find(b => b.id === current)?.name ?? "current"}` : ""}</option><option value="selected">Selected branches</option><option value="all" disabled={!canAll}>All branches</option></NativeSelect></label>
    {scope === "selected" && writable.map(branch => <label key={branch.id} className="flex items-center gap-2 text-sm"><input type="checkbox" style={{ width: 16, height: 16 }} checked={choice?.branch_ids.includes(branch.id) ?? false} disabled={branch.id === current} onChange={e => onChange({ scope: "selected", branch_ids: e.target.checked ? [...(choice?.branch_ids ?? []), branch.id] : (choice?.branch_ids ?? []).filter(id => id !== branch.id) })}/>{branch.name}{branch.id === current ? " (current)" : ""}</label>)}
    <p className="text-xs text-muted-foreground">All branches includes current active branches. New branches must be added later. The same master is available in the chosen branches. Transactions and stock stay in their original branches.</p>
    {editing && resource && <p className="text-xs text-muted-foreground">Change profile availability from its owning branch.</p>}
    {!canAll && ready && <p className="text-xs text-muted-foreground">All branches requires write access to every active branch.</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
  </fieldset>;
}
