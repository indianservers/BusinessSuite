import { useDeferredValue, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import AdminVerification, { administratorStepUp } from "@/features/access/AdminVerification";

type Account = { id: number; email: string; role_id: number | null; role: string | null; is_superuser: boolean;
  status: string; employee_name: string | null; employee_code: string | null; employee_id: number | null;
  last_login: string | null; mfa_enabled: boolean; version: string };
type Role = { id: number; name: string; description: string; is_system: boolean; permission_ids: number[]; version: string };
type Permission = { id: number; name: string; module: string; description: string };
type Editor = { kind: string; user?: Account; role?: Role };
const root = "/employees/accounts";
const selectClass = "h-10 rounded-md border bg-background px-3 text-sm";
const titles: Record<string, string> = { create: "Create login account", edit: "Edit account", reset_password: "Reset password",
  suspended: "Suspend access", terminated: "Terminate access", active: "Reactivate account", revoke_sessions: "Sign out all sessions", role: "Custom role" };

export default function UserAccountsPage() {
  const actor = useAuthStore(state => state.user);
  const allowed = actor?.is_superuser === true;
  const [url] = useSearchParams();
  const [search, setSearch] = useState(url.get("search") || "");
  const deferredSearch = useDeferredValue(search);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [tab, setTab] = useState("accounts");
  const [editor, setEditor] = useState<Editor | null>(null);
  const [historyUser, setHistoryUser] = useState<Account | null>(null);
  const [reason, setReason] = useState("");
  const [verification, setVerification] = useState("");
  const [form, setForm] = useState({ email: "", password: "", role_id: "", employee_id: "", is_superuser: false,
    name: "", description: "", permission_ids: [] as number[] });
  const [permissionSearch, setPermissionSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const qc = useQueryClient();
  const options = useQuery({ queryKey: ["hrms-account-options"], enabled: allowed,
    queryFn: () => api.get(root + "/options").then(r => r.data as { roles: Role[]; permissions: Permission[]; employees: {id: number; name: string}[] }) });
  const accounts = useQuery({ queryKey: ["hrms-accounts", deferredSearch, status, roleFilter, page], enabled: allowed,
    queryFn: () => api.get(root, { params: { search: deferredSearch, status, role_id: roleFilter || undefined, page } }).then(r => r.data as { items: Account[]; total: number; per_page: number }) });
  const history = useQuery({ queryKey: ["hrms-account-history", historyUser?.id], enabled: allowed && !!historyUser,
    queryFn: () => api.get(`${root}/${historyUser!.id}/history`).then(r => r.data as {id: number; action: string; reason: string; actor: string; created_at: string}[]) });

  function open(kind: string, user?: Account, role?: Role, clone = false) {
    setEditor({ kind, user, role: clone ? undefined : role });
    setForm({ email: user?.email || "", password: "", role_id: user?.role_id?.toString() || "", employee_id: "",
      is_superuser: user?.is_superuser || false, name: role ? role.name + (clone ? " copy" : "") : "",
      description: role?.description || "", permission_ids: role?.permission_ids || [] });
    setReason(""); setVerification(""); setPermissionSearch(""); setError(""); setMessage("");
  }
  function close() { if (!busy) { setEditor(null); setForm(current => ({ ...current, password: "" })); setVerification(""); } }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!editor) return;
    setBusy(true); setError("");
    try {
      const step = await administratorStepUp(verification);
      const config = { headers: { "X-Access-Step-Up": step.data.token } };
      if (editor.kind === "role") {
        const payload = { name: form.name, description: form.description, permission_ids: form.permission_ids,
          reason, version: editor.role?.version || null };
        if (editor.role) await api.put(`${root}/roles/${editor.role.id}`, payload, config);
        else await api.post(root + "/roles", payload, config);
      } else if (editor.kind === "create") {
        await api.post(root, { email: form.email, password: form.password, role_id: form.role_id ? Number(form.role_id) : null,
          employee_id: form.employee_id ? Number(form.employee_id) : null, is_superuser: form.is_superuser, reason }, config);
      } else if (editor.kind === "edit") {
        await api.patch(`${root}/${editor.user!.id}`, { email: form.email, role_id: form.role_id ? Number(form.role_id) : null,
          is_superuser: form.is_superuser, version: editor.user!.version, reason }, config);
      } else {
        await api.post(`${root}/${editor.user!.id}/actions`, { action: editor.kind, version: editor.user!.version,
          reason, ...(editor.kind === "reset_password" ? { password: form.password } : {}) }, config);
      }
      setEditor(null); setForm(current => ({ ...current, password: "" })); setVerification("");
      setMessage("Change saved and recorded in the audit history. Existing sessions were revoked where applicable.");
      await Promise.all([qc.invalidateQueries({ queryKey: ["hrms-accounts"] }), qc.invalidateQueries({ queryKey: ["hrms-account-options"] }),
        qc.invalidateQueries({ queryKey: ["employee"] }), qc.invalidateQueries({ queryKey: ["employee-user-options"] })]);
    } catch (failure: any) {
      setError(typeof failure?.response?.data?.detail === "string" ? failure.response.data.detail : "Could not save this change. Check the values and try again.");
    } finally { setBusy(false); setVerification(""); }
  }

  if (!allowed) return <div role="alert" className="p-6">Super Admin access is required to manage HRMS accounts and roles.</div>;
  const permissions = (options.data?.permissions || []).filter(p => `${p.module} ${p.name} ${p.description}`.toLowerCase().includes(permissionSearch.toLowerCase()));
  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div>
      <h1 className="page-title">Users &amp; Roles</h1><p className="page-description">Super Admin control over login accounts, permissions and access across the suite.</p>
      <Link className="text-sm underline" to="/hrms/employees">Back to employees</Link>
    </div><div className="flex gap-2"><Button variant="outline" onClick={() => { void accounts.refetch(); void options.refetch(); }}>Refresh</Button>
      <Button onClick={() => open("create")} disabled={!options.data}>Create user</Button></div></div>
    {message && <p role="status" className="rounded border p-3 text-sm">{message}</p>}
    <nav className="flex gap-2" aria-label="Account administration"><Button variant={tab === "accounts" ? "default" : "outline"} onClick={() => setTab("accounts")}>User accounts</Button>
      <Button variant={tab === "roles" ? "default" : "outline"} onClick={() => setTab("roles")}>Roles &amp; permissions</Button></nav>
    {(accounts.isError || options.isError) && <p role="alert">Could not load account administration. Use Refresh to retry.</p>}
    {tab === "accounts" ? <Card><CardHeader><CardTitle>User accounts</CardTitle>
      <div className="flex flex-wrap gap-2"><Input className="max-w-sm" aria-label="Search accounts" placeholder="Email, employee name or code" value={search} onChange={e => {setSearch(e.target.value); setPage(1);}} />
        <select aria-label="Filter account status" className={selectClass} value={status} onChange={e => {setStatus(e.target.value);setPage(1);}}><option value="">All statuses</option>{["active", "inactive", "suspended", "terminated"].map(s => <option key={s}>{s}</option>)}</select>
        <select aria-label="Filter account role" className={selectClass} value={roleFilter} onChange={e => {setRoleFilter(e.target.value);setPage(1);}}><option value="">All roles</option>{options.data?.roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></div>
    </CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b">{["Account", "Employee", "Role", "Access", "Security", "Actions"].map(h => <th key={h} className="p-3">{h}</th>)}</tr></thead>
      <tbody>{accounts.data?.items.map(user => <tr key={user.id} className="border-b"><td className="p-3 font-medium">{user.email}{user.id === actor?.id && <span className="ml-2 text-xs">(you)</span>}</td>
        <td className="p-3">{user.employee_name || "Not linked"}<div className="text-xs text-muted-foreground">{user.employee_code}</div></td>
        <td className="p-3">{user.role || "No role"}{user.is_superuser && <div className="font-semibold">Global Super Admin</div>}</td><td className="p-3 capitalize">{user.status}</td>
        <td className="p-3"><div>MFA {user.mfa_enabled ? "enabled" : "not enabled"}</div><div className="text-xs text-muted-foreground">Last login: {user.last_login ? new Date(user.last_login).toLocaleString() : "Never"}</div></td>
        <td className="p-3"><select aria-label={`Manage ${user.email}`} className={selectClass} value="" onChange={e => {if(e.target.value === "history") setHistoryUser(user);else if(e.target.value) open(e.target.value,user);}}>
          <option value="">Choose action</option><option value="edit">Edit email, role &amp; Super Admin</option><option value="reset_password">Reset password</option>
          {user.status === "active" ? <><option value="suspended" disabled={user.id === actor?.id}>Suspend access</option><option value="terminated" disabled={user.id === actor?.id}>Terminate access</option></> : <option value="active">Reactivate access</option>}
          <option value="revoke_sessions">Sign out all sessions</option><option value="history">View audit history</option></select></td></tr>)}</tbody></table></div>
      {accounts.isLoading ? <p className="p-3">Loading accounts…</p> : !accounts.data?.items.length && <p className="p-3">No matching accounts.</p>}
      <div className="mt-4 flex items-center justify-between"><span>{accounts.data?.total || 0} accounts · Page {page}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => setPage(page-1)}>Previous</Button><Button variant="outline" disabled={!accounts.data || page * accounts.data.per_page >= accounts.data.total} onClick={() => setPage(page+1)}>Next</Button></div></div>
    </CardContent></Card> : <Card><CardHeader><div className="flex items-center justify-between"><CardTitle>Roles &amp; permissions</CardTitle><Button onClick={() => open("role")}>Create custom role</Button></div><p className="text-sm text-muted-foreground">Built-in roles are preserved. Clone one to customize its permissions, then assign the custom role to users.</p></CardHeader>
      <CardContent className="space-y-3">{options.data?.roles.map(role => <div key={role.id} className="flex flex-wrap justify-between gap-3 rounded border p-3"><div><strong>{role.name}</strong>{role.is_system && <span className="ml-2 text-xs">Built-in</span>}<p className="text-sm text-muted-foreground">{role.description}</p><p className="text-xs">{role.permission_ids.length} permissions</p></div><div className="flex gap-2">{!role.is_system && <Button variant="outline" onClick={() => open("role",undefined,role)}>Edit</Button>}<Button variant="outline" onClick={() => open("role",undefined,role,true)}>Clone role</Button></div></div>)}</CardContent></Card>}
    <Dialog open={!!editor} onOpenChange={value => {if(!value)close();}}><DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto"><DialogTitle>{editor ? titles[editor.kind] : "Manage account"}</DialogTitle>
      {editor && <form onSubmit={save} className="space-y-4">
        {editor.user && <p className="font-medium">{editor.user.email}</p>}
        {["create", "edit"].includes(editor.kind) && <>
          <label className="block space-y-1">Login email<Input type="email" autoComplete="off" required value={form.email} onChange={e => setForm({...form,email:e.target.value})} /></label>
          <label className="block space-y-1">Account role<select required={editor.kind === "create" && !form.is_superuser} className={selectClass + " w-full"} value={form.role_id} onChange={e => setForm({...form,role_id:e.target.value})}><option value="">{editor.kind === "create" ? "Select a role" : "No role"}</option>{options.data?.roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
          {editor.kind === "create" && <label className="block space-y-1">Link employee or intern (optional)<select className={selectClass + " w-full"} value={form.employee_id} onChange={e => setForm({...form,employee_id:e.target.value})}><option value="">Create an account without an employee link</option>{options.data?.employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label>}
          <label className="flex items-start gap-2 rounded border p-3"><input type="checkbox" checked={form.is_superuser} disabled={editor.user?.id === actor?.id && editor.user?.is_superuser} onChange={e => setForm({...form,is_superuser:e.target.checked})} /><span>Global Super Admin<p className="text-xs text-muted-foreground">Grants access to all companies, users and installed modules.</p></span></label>
        </>}
        {["create", "reset_password"].includes(editor.kind) && <label className="block space-y-1">{editor.kind === "create" ? "Initial password" : "New Business Suite password"}<Input type="password" autoComplete="new-password" minLength={8} required value={form.password} onChange={e => setForm({...form,password:e.target.value})} /><p className="text-xs text-muted-foreground">Your organization's password policy applies. Google and Microsoft passwords are managed by their providers.</p></label>}
        {["suspended", "terminated"].includes(editor.kind) && <p className="rounded border p-3 text-sm">This blocks sign-in across the suite and revokes existing sessions. Employee records and audit history are retained. A Super Admin can reactivate access.</p>}
        {editor.kind === "active" && <p className="text-sm">Re-enables sign-in. Existing organization and module policies continue to apply.</p>}
        {editor.kind === "revoke_sessions" && <p className="text-sm">Signs the account out of existing sessions. It can sign in again if its access is active.</p>}
        {editor.kind === "role" && <>
          <label className="block space-y-1">Role name<Input required minLength={2} maxLength={50} value={form.name} onChange={e => setForm({...form,name:e.target.value})} /></label>
          <label className="block space-y-1">Description<Input maxLength={1000} value={form.description} onChange={e => setForm({...form,description:e.target.value})} /></label>
          <Input aria-label="Search permissions" placeholder="Search permissions or module" value={permissionSearch} onChange={e => setPermissionSearch(e.target.value)} />
          <p className="text-sm">{form.permission_ids.length} permissions selected</p><div className="max-h-60 space-y-2 overflow-auto rounded border p-3">{permissions.map(p => <label key={p.id} className="flex items-start gap-2"><input type="checkbox" checked={form.permission_ids.includes(p.id)} onChange={e => setForm({...form,permission_ids:e.target.checked ? [...form.permission_ids,p.id] : form.permission_ids.filter(id => id !== p.id)})} /><span className="text-sm">{p.name}<span className="ml-2 text-xs text-muted-foreground">{p.module}</span><p className="text-xs text-muted-foreground">{p.description}</p></span></label>)}</div>
          {editor.role && <p className="text-sm">Saving changes signs out users assigned to this role so their next session uses the updated permissions.</p>}
        </>}
        <label className="block space-y-1">Reason for this change<Input required minLength={3} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <AdminVerification value={verification} onChange={setVerification} />
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={busy} onClick={close}>Cancel</Button><Button disabled={busy || reason.trim().length < 3 || !options.data}>{busy ? "Saving…" : "Verify & save"}</Button></div>
      </form>}
    </DialogContent></Dialog>
    <Dialog open={!!historyUser} onOpenChange={value => {if(!value)setHistoryUser(null);}}><DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto"><DialogTitle>Account audit history</DialogTitle><p>{historyUser?.email}</p>
      {history.isLoading ? <p>Loading history…</p> : history.isError ? <p role="alert">Could not load history.</p> : <div className="space-y-3">{history.data?.map(row => <div key={row.id} className="rounded border p-3 text-sm"><strong>{row.action.replace(/_/g," ")}</strong><p>{row.reason}</p><p className="text-xs text-muted-foreground">{row.actor} · {new Date(row.created_at).toLocaleString()}</p></div>)}{!history.data?.length && <p>No account administration events recorded yet.</p>}</div>}
    </DialogContent></Dialog>
  </div>;
}
