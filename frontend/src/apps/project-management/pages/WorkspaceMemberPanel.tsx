import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "./workspaceTypes";

type Person = { id: number; user_id: number; name?: string; email: string; role: string };
type Command = { kind: "add"; user: number } | { kind: "role"; member: number; role: string } | { kind: "remove"; member: number };
export function WorkspaceMemberPanel({ id, canManage }: { id: string; canManage: boolean }) {
  const qc = useQueryClient();
  const user = useAuthStore(state => state.user);
  const scope = JSON.stringify([user?.id, user?.role, user?.is_superuser, user?.access, sessionStorage.getItem("suite-branch")]);
  const key = ["pms-workspace-team", id, scope];
  const base = `/project-management/workspaces/${id}`;
  const query = useQuery({ queryKey: key, queryFn: ({ signal }) => api.get<Person[]>(`${base}/members`, { signal }).then(response => response.data), retry: false });
  const denied = [401, 403, 404].includes((query.error as { response?: { status?: number } } | null)?.response?.status || 0);
  const rows = denied ? [] : query.data || [];
  const [email, setEmail] = useState("");
  const [inviteCompletion, setInviteCompletion] = useState(0);
  const [showAdd, setShowAdd] = useState(false);
  const [person, setPerson] = useState("");
  const [personSearch, setPersonSearch] = useState("");
  const [invitation, setInvitation] = useState("");
  const [copyNotice, setCopyNotice] = useState("");
  const eligible = useQuery({ queryKey: ["pms-workspace-eligible", id, scope], enabled: canManage && showAdd, queryFn: ({ signal }) => api.get<{ user_id: number; email: string }[]>("/project-management/workspace-directory/eligible-people", { signal, params: { ref: id } }).then(response => response.data), retry: false });
  const invite = useMutation({ mutationFn: () => api.post<{ token?: string }>(`${base}/invitations`, { email: email.trim(), role: "Member" }), onSuccess: response => { setInviteCompletion(value=>value+1); setEmail(""); if (response.data.token) setInvitation(`${window.location.origin}/pms/invitation?token=${encodeURIComponent(response.data.token)}`); } });
  const change = useMutation({ mutationFn: (command: Command) => command.kind === "add" ? api.post(`${base}/members`, { user_id: command.user, role: "Member" }) : command.kind === "remove" ? api.delete(`${base}/members/${command.member}`) : api.patch(`${base}/members/${command.member}`, { role: command.role }), onSuccess: () => { setShowAdd(false); setPerson(""); void qc.invalidateQueries({ queryKey: key }); } });
  return <section className="wd-activity"><h2>Workspace team</h2>
    {query.isPending && <p role="status">Loading members…</p>}
    {query.isError && <p role="alert">{workspaceError(query.error)}<Button onClick={() => void query.refetch()} variant="ghost">Retry members</Button></p>}
    {rows.map(member => <div className="wd-member-edit" key={member.id}><span>{member.name || member.email}<small className="block text-muted-foreground">{member.email}</small></span>{canManage && member.role !== "Owner" ? <><select aria-label={`Role for ${member.email}`} disabled={change.isPending} value={member.role} onChange={event => change.mutate({ kind: "role", member: member.id, role: event.target.value })}><option>Admin</option><option>Member</option><option>Guest</option></select><Button variant="ghost" size="sm" disabled={change.isPending} onClick={() => change.mutate({ kind: "remove", member: member.id })}>Remove</Button></> : <span>{member.role}</span>}</div>)}
    {change.isError && <p role="alert">{workspaceError(change.error)}</p>}
    {canManage && !denied && <><div className="wd-team-actions"><Button variant="outline" onClick={() => setShowAdd(value => !value)}>Add existing person</Button></div>{showAdd && <SmartCreateSection title="Add existing workspace member" autoOpen closeOnRecordSaved={false} onClose={()=>setShowAdd(false)}><form className="wd-invite-form" onSubmit={event => { event.preventDefault(); if (person) change.mutate({ kind: "add", user: Number(person) }); }}><label>Add person to workspace<Input aria-label="Search existing workspace people" placeholder="Search by email" value={personSearch} onChange={event => setPersonSearch(event.target.value)}/><select aria-label="Existing workspace person" value={person} onChange={event => setPerson(event.target.value)} required><option value="">Choose a person</option>{eligible.data?.filter(candidate => candidate.email.toLowerCase().includes(personSearch.trim().toLowerCase()) && !rows.some(member => member.user_id === candidate.user_id)).map(candidate => <option value={candidate.user_id} key={candidate.user_id}>{candidate.email}</option>)}</select></label>{eligible.isFetching && <p role="status">Checking eligible people…</p>}{eligible.isError && <p role="alert">People could not load.<Button variant="ghost" type="button" onClick={() => void eligible.refetch()}>Retry people</Button></p>}<Button data-save-action disabled={!person || change.isPending}>Add member</Button></form></SmartCreateSection>}
    <SmartCreateSection title="Invite workspace member" completionRevision={inviteCompletion} closeOnRecordSaved={false}><form className="wd-invite-form" onSubmit={event => { event.preventDefault(); invite.mutate(); }}><label>Invite a member<Input type="email" required aria-label="Invite member email" value={email} onChange={event => setEmail(event.target.value)} /></label><Button data-save-action disabled={invite.isPending || !email.trim()}>Invite member</Button>{invite.isError && <p role="alert">{workspaceError(invite.error)}</p>}{invite.isSuccess && <p role="status">Invitation created. Existing users can accept it from their invitation inbox.</p>}</form></SmartCreateSection>
    {invitation && <div className="wd-invite-form"><label>Private invitation link<Input readOnly value={invitation} /></label><Button variant="outline" onClick={() => { void navigator.clipboard.writeText(invitation).then(() => setCopyNotice("Invitation link copied.")).catch(() => setCopyNotice("Select the link to copy it manually.")); }}>Copy invitation link</Button>{copyNotice && <p role="status">{copyNotice}</p>}</div>}</>}
  </section>;
}
