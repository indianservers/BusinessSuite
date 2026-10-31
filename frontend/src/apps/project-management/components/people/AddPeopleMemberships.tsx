import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { PeopleDialog } from "./DirectoryDialogs";
import { peopleBase, peopleChanged } from "./peopleTypes";
import { membershipOptionsKey, useMembershipOptions } from "./peopleMemberships";
import { workspaceError } from "../../pages/workspaceTypes";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

export default function AddPeopleMemberships({ mode, personIds, onClose, onAdded }: {
  mode: "workspace" | "project" | null;
  personIds: number[];
  onClose: () => void;
  onAdded: () => void;
}) {
  const qc = useQueryClient();
  const user = useAuthStore(state => state.user);
  const options = useMembershipOptions(!!mode);
  const [destinations, setDestinations] = useState<number[]>([]);
  const [role, setRole] = useState("Member");
  const [reason, setReason] = useState("Added from people directory");
  const [busy, setBusy] = useState(false);
  const [submittedCount, setSubmittedCount] = useState(0);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [result, setResult] = useState<{ added: unknown[]; already_present: number; warnings: string[]; results?: { user_id: number; email: string; destination_type: string; destination_name: string; status: string }[] } | null>(null);
  useEffect(() => {
    setDestinations([]); setRole("Member"); setReason("Added from people directory"); setError(""); setResult(null); setSubmittedCount(0); setSearch("");
  }, [mode]);
  const choices = mode === "project" ? options.data?.projects : options.data?.workspaces;
  const combinations = personIds.length * destinations.length;
  const tooMany = combinations > 500 || destinations.length > (mode === "workspace" ? 30 : 100);
  const count = result ? submittedCount : personIds.length;
  return <PeopleDialog open={!!mode} onClose={() => { if (!busy) onClose(); }}
    title={mode === "project" ? "Add to project" : "Add to workspace"}
    description={`Add ${count} selected ${count === 1 ? "person" : "people"} directly to ${mode === "project" ? "project teams" : "workspaces"} you manage.`}>
    {result ? <div role="status" className="space-y-3">
      <p>{result.added.length} memberships added. {result.already_present} memberships already existed.</p>
      {!!result.warnings.length && <p>{result.warnings.length} {result.warnings.length === 1 ? "person needs" : "people need"} an organization access review. See the account-specific messages below.</p>}
      <div className="max-h-64 overflow-auto"><table className="w-full text-left text-sm"><thead><tr><th>Person</th><th>Destination</th><th>Result</th></tr></thead><tbody>{result.results?.map((row,index) => <tr key={index} className="border-t"><td className="p-2">{row.email}</td><td className="p-2">{row.destination_name} ({row.destination_type})</td><td className="p-2">{row.status === "added" ? "Added" : "Already a member"}</td></tr>)}</tbody></table></div>
      {result.warnings.map((warning, index) => <p key={index} className="pd-error">{warning}</p>)}
      {!!result.warnings.length && (user?.is_superuser || user?.access?.isAccessAdmin) && <Link className="pd-button" to="/admin/access">Review organization access</Link>}
      <button type="button" className="pd-button primary" onClick={onClose}>Done</button>
    </div> : <form onSubmit={async event => {
      event.preventDefault();
      if (!destinations.length || !personIds.length || tooMany) return;
      setBusy(true); setError(""); setSubmittedCount(personIds.length);
      try {
        const { data } = await api.post(`${peopleBase}/memberships/bulk`, {
          user_ids: personIds,
          workspace_ids: mode === "workspace" ? destinations : [],
          project_ids: mode === "project" ? destinations : [],
          role: mode === "workspace" ? role : "Member",
          reason: reason.trim(),
        });
        setResult(data);
        await qc.invalidateQueries({ queryKey: ["people-workspace"] });
        await qc.invalidateQueries({ queryKey: membershipOptionsKey });
        peopleChanged(); onAdded();
      } catch (e) { setError(workspaceError(e)); }
      finally { setBusy(false); }
    }}>
      {error && <p role="alert" className="pd-error">{error}</p>}
      {options.isLoading && <p role="status">Loading available {mode === "project" ? "projects" : "workspaces"}…</p>}
      {options.isError && <p role="alert">Could not load destinations. <button type="button" onClick={() => options.refetch()}>Retry</button></p>}
      <fieldset disabled={busy || options.isLoading || options.isError} className="space-y-4">
        <label className="block">Search {mode === "project" ? "projects" : "workspaces"}<input className="mt-1 block w-full rounded border p-2" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name or project key" /></label>
        <p>{destinations.length} destinations selected</p>
        <div className="max-h-64 space-y-2 overflow-y-auto" role="group" aria-label={`Choose ${mode === "project" ? "projects" : "workspaces"}`}>
          {choices?.filter(choice => `${choice.name} ${"project_key" in choice ? choice.project_key : ""}`.toLowerCase().includes(search.toLowerCase())).map(choice => <label key={choice.id} className="flex items-center gap-2 rounded border p-3">
            <input type="checkbox" checked={destinations.includes(choice.id)} onChange={event => setDestinations(current => event.target.checked ? [...current, choice.id] : current.filter(id => id !== choice.id))} />
            <span>{choice.name}{"project_key" in choice && choice.project_key ? ` (${choice.project_key})` : ""}</span>
          </label>)}
          {choices?.length === 0 && <p>No {mode === "project" ? "projects" : "workspaces"} available for you to manage.</p>}
          {!!choices?.length && !choices.some(choice => `${choice.name} ${"project_key" in choice ? choice.project_key : ""}`.toLowerCase().includes(search.toLowerCase())) && <p>No matching destinations. <button type="button" onClick={() => setSearch("")}>Clear search</button></p>}
        </div>
        {mode === "workspace" ? <label className="block">Workspace role
          <select className="mt-1 block w-full rounded border p-2" value={role} onChange={event => setRole(event.target.value)}>
            <option value="Member">Member</option><option value="Guest">Guest</option>
          </select>
        </label> : <p>People are added as project Members. Required workspace membership is added automatically. Existing roles remain unchanged.</p>}
        <label className="block">Reason
          <input className="mt-1 block w-full rounded border p-2" required minLength={3} maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} />
        </label>
        {tooMany && <p role="alert" className="pd-error">Choose fewer destinations. A single operation supports at most {mode === "workspace" ? 30 : 100} destinations and 500 person/destination combinations.</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="pd-button" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="pd-button primary" disabled={busy || !destinations.length || !personIds.length || tooMany || reason.trim().length < 3}>{busy ? "Adding…" : `Add to ${mode}`}</button>
        </div>
      </fieldset>
    </form>}
  </PeopleDialog>;
}
