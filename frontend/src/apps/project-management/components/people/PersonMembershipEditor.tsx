import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { api } from "@/services/api";
import { peopleBase, type Membership } from "./peopleTypes";
import { useMembershipOptions } from "./peopleMemberships";

type Props = {
  person: { id: number; status: string; workspaces: Membership[]; projects: Membership[]; permissions: Record<string, boolean> };
  busy: boolean;
  mutate: (work: () => Promise<unknown>, message: string) => Promise<boolean>;
  remove: (action: { kind: "remove_workspace" | "remove_project"; workspaceId?: number; projectId?: number }) => void;
};

export default function PersonMembershipEditor({ person, busy, mutate, remove }: Props) {
  const options = useMembershipOptions();
  const [kind, setKind] = useState<"workspace" | "project">("workspace");
  const [destination, setDestination] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("Member");
  const [membershipSearch, setMembershipSearch] = useState("");
  const choices = (kind === "workspace" ? options.data?.workspaces : options.data?.projects) || [];
  const memberships = kind === "workspace" ? person.workspaces : person.projects;
  const available = choices.filter(choice => !memberships.some(m => (kind === "workspace" ? m.workspace_id : m.project_id) === choice.id));
  const matches = available.filter(choice => choice.name.toLowerCase().includes(search.toLowerCase()));
  const canAdd = person.permissions.memberships && person.status === "active";
  const base = "/project-management";

  return <div className="space-y-4">
    {canAdd && <section aria-label="Add membership" className="space-y-3 rounded-xl border bg-muted/30 p-3">
      <div className="flex gap-2" role="group" aria-label="Assignment destination type">
        <Button size="sm" variant={kind === "workspace" ? "default" : "outline"} disabled={busy} onClick={() => { setKind("workspace"); setDestination(""); setRole("Member"); setSearch(""); }}>Workspace</Button>
        <Button size="sm" variant={kind === "project" ? "default" : "outline"} disabled={busy} onClick={() => { setKind("project"); setDestination(""); setRole("Member"); setSearch(""); }}>Project</Button>
      </div>
      {options.isError ? <p role="alert" className="text-sm">Could not load available destinations. <button className="underline" onClick={() => void options.refetch()}>Retry</button></p> : <>
        <Input aria-label="Search assignment destinations" placeholder={`Find a ${kind}…`} value={search} disabled={busy} onChange={e => { setSearch(e.target.value); setDestination(""); }} />
        <div className="flex flex-wrap items-end gap-2">
          <label className="min-w-0 flex-1 text-sm">{kind === "workspace" ? "Workspace" : "Project"}
            <NativeSelect className="mt-1 w-full rounded-md border bg-background p-2" aria-label="Assignment destination" value={destination} disabled={busy || options.isLoading} onChange={e => setDestination(e.target.value)}>
              <option value="">{options.isLoading ? "Loading destinations…" : `Choose a ${kind}`}</option>
              {matches.map(choice => <option key={choice.id} value={choice.id}>{choice.name}{kind === "project" && "workspace_id" in choice ? ` · ${options.data?.workspaces.find(w => w.id === choice.workspace_id)?.name || "Organization project"}` : ""}</option>)}
            </NativeSelect>
          </label>
          {kind === "workspace" && <label className="text-sm">Role<NativeSelect aria-label="New workspace role" className="mt-1 rounded-md border bg-background p-2" value={role} disabled={busy} onChange={e => setRole(e.target.value)}><option>Member</option><option>Guest</option></NativeSelect></label>}
          <Button disabled={busy || !destination || options.isError || options.isLoading} onClick={async () => {
            const saved = await mutate(() => api.post(`${peopleBase}/memberships/bulk`, { user_ids: [person.id], workspace_ids: kind === "workspace" ? [Number(destination)] : [], project_ids: kind === "project" ? [Number(destination)] : [], role: kind === "workspace" ? role : "Member", reason: "Assigned from employee directory" }), `${kind === "workspace" ? "Workspace" : "Project"} assignment added`);
            if (saved) { setDestination(""); setSearch(""); }
          }}>{busy ? "Saving…" : "Assign"}</Button>
        </div>
        {!options.isLoading && !matches.length && <p className="text-xs text-muted-foreground">{available.length ? "No matching destinations." : `No additional ${kind === "workspace" ? "workspaces" : "projects"} available in your management scope.`}</p>}
        {kind === "project" && <p className="text-xs text-muted-foreground">Required workspace membership is included when you assign a project.</p>}
      </>}
    </section>}
    <Input aria-label="Filter current memberships" placeholder="Find an existing workspace or project…" value={membershipSearch} onChange={e => setMembershipSearch(e.target.value)} />
    {(["workspace", "project"] as const).map(type => {
      const rows = type === "workspace" ? person.workspaces : person.projects;
      const visible = rows.filter(row => row.name.toLowerCase().includes(membershipSearch.toLowerCase()));
      return <section key={type} aria-label={type === "workspace" ? "Current workspaces" : "Current projects"} className="space-y-2">
        <h3 className="text-sm font-semibold">{type === "workspace" ? "Workspaces" : "Projects"} <span className="text-muted-foreground">({rows.length})</span></h3>
        {!visible.length && <p className="text-sm text-muted-foreground">{rows.length ? "No matching memberships." : `No ${type} memberships.`}</p>}
        {visible.map(membership => {
          const editable = membership.can_remove === true && person.permissions.memberships && membership.role !== "Owner";
          const workspace = options.data?.workspaces.find(w => w.id === membership.workspace_id);
          const roles = type === "workspace" ? ["Member", "Guest", ...(workspace?.can_appoint_admin ? ["Admin"] : [])] : ["Admin", "Manager", "Member", "Viewer", "Client"];
          return <article key={membership.id} className="flex flex-wrap items-center gap-2 rounded-lg border p-3">
            <div className="min-w-0 flex-1"><p className="break-words text-sm font-medium">{membership.name}</p>{type === "project" && <p className="text-xs text-muted-foreground">{person.workspaces.find(w => w.workspace_id === membership.workspace_id)?.name || "Organization project"}</p>}{!editable && membership.unavailable_reason && <p className="text-xs text-muted-foreground">{membership.unavailable_reason}</p>}</div>
            <NativeSelect aria-label={`Role in ${membership.name}`} className="max-w-36 rounded-md border bg-background p-1.5 text-sm" disabled={busy || !editable || options.isLoading || options.isError} value={membership.role} onChange={e => void mutate(() => api.patch(`${base}/${type === "workspace" ? "workspaces" : "projects"}/${type === "workspace" ? membership.workspace_id : membership.project_id}/members/${membership.id}`, { role: e.target.value }), "Membership role updated")}>
              {[...new Set([membership.role, ...roles])].map(value => <option key={value}>{value}</option>)}
            </NativeSelect>
            <Button size="sm" variant="outline" disabled={busy || !editable} aria-label={`Remove from ${membership.name}`} onClick={() => remove({ kind: type === "workspace" ? "remove_workspace" : "remove_project", workspaceId: type === "workspace" ? membership.workspace_id : undefined, projectId: type === "project" ? membership.project_id : undefined })}>Remove</Button>
          </article>;
        })}
      </section>;
    })}
    <p className="text-xs text-muted-foreground">Only memberships visible to your account are shown. Workspace access can include projects beyond the explicitly assigned project teams.</p>
  </div>;
}
