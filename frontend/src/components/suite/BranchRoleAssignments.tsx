import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import AdminVerification, { administratorStepUp } from "@/features/access/AdminVerification";

type Grant = { enabled: boolean; role: string; permissions: string[]; actions: string[]; scope: string; roleId?: number | null };
type CustomRole = { id: number; name: string; module_key: string; permissions: string[]; actions: string[]; scope: string };
type Policy = { version: number; all_branches: boolean; manage_access: boolean; use_home_branch: boolean; grants: { branch_id: number; can_write: boolean; module_grants?: Record<string, Grant> | null }[] };

export default function BranchRoleAssignments({ userId, companyId, enabledModules }: { userId: number; companyId: number; enabledModules: string[] }) {
  const [draft, setDraft] = useState<Policy | null>(null);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [verification, setVerification] = useState("");
  const headers = { "X-Suite-Organization": String(companyId), "X-Suite-Branch": "all" };
  const policy = useQuery<Policy>({ queryKey: ["branch-roles", companyId, userId], queryFn: async () => (await api.get(`/branches/access/${userId}`, { headers })).data });
  const branches = useQuery<{ branches: { id: number; name: string; is_active: boolean }[] }>({ queryKey: ["branch-role-choices", companyId], queryFn: async () => (await api.get("/branches/context", { headers })).data });
  const catalog = useQuery<{ modules: { key: string; label: string; installed: boolean }[]; presets: Record<string, Record<string, Grant>>; roles: CustomRole[] }>({ queryKey: ["branch-role-catalog", companyId], queryFn: async () => (await api.get("/access/catalog", { params: { companyId } })).data });
  const value = draft || policy.data;
  if (policy.isError || branches.isError || catalog.isError) return <p role="alert">Unable to load branch roles.</p>;
  if (!value || !branches.data || !catalog.data) return <p>Loading branch roles…</p>;
  const change = (id: number, patch: object) => setDraft({ ...value, grants: value.grants.map(g => g.branch_id === id ? { ...g, ...patch } : g) });
  return <section className="my-4 grid gap-3 rounded-lg border p-4">
    <h3 className="font-semibold">Branch memberships & roles</h3>
    <p className="text-sm text-muted-foreground">First save the company module permissions below as the maximum access. Here, choose a different role for each branch. Unselected modules have no access when branch roles are enabled.</p>
    <label><input type="checkbox" checked={value.use_home_branch} onChange={e => setDraft({ ...value, use_home_branch: e.target.checked })} /> Automatically allow employee’s home branch</label>
    <label><input type="checkbox" checked={value.all_branches} onChange={e => setDraft({ ...value, all_branches: e.target.checked })} /> All current and future branches</label>
    <label><input type="checkbox" checked={value.manage_access} onChange={e => setDraft({ ...value, manage_access: e.target.checked })} /> May administer branch memberships</label>
    {branches.data.branches.filter(b => b.is_active).map(branch => {
      const grant = value.grants.find(g => g.branch_id === branch.id);
      return <div key={branch.id} className="grid gap-3 rounded border p-3">
        <label className="font-medium"><input aria-label={`Allow ${branch.name}`} type="checkbox" checked={!!grant} onChange={e => setDraft({ ...value, grants: e.target.checked ? [...value.grants, { branch_id: branch.id, can_write: false, module_grants: {} }] : value.grants.filter(g => g.branch_id !== branch.id) })} /> {branch.name}</label>
        {grant && <>
          <label><input type="checkbox" checked={grant.can_write} onChange={e => change(branch.id, { can_write: e.target.checked })} /> Allow writes permitted by module role</label>
          <label><input type="checkbox" checked={grant.module_grants == null} onChange={e => change(branch.id, { module_grants: e.target.checked ? null : {} })} /> Inherit company module roles</label>
          {grant.module_grants != null && <div className="grid gap-2 sm:grid-cols-2">{catalog.data!.modules.filter(m => m.installed && (enabledModules.includes(m.key) || grant.module_grants?.[m.key]?.enabled)).map(module => {
            const selected = grant.module_grants?.[module.key];
            return <label key={module.key} className="grid gap-1 text-sm">{module.label}<select aria-label={`${branch.name} ${module.label} role`} className="rounded border bg-background p-2" value={selected?.enabled ? selected.roleId ? `custom:${selected.roleId}` : selected.role : "none"} onChange={e => {
              const modules = { ...grant.module_grants };
              if (e.target.value === "none") delete modules[module.key];
              else if (e.target.value.startsWith('custom:')) {
                const role = catalog.data!.roles.find(r => r.id === Number(e.target.value.split(':')[1]));
                if (role) modules[module.key] = { enabled: true, role: role.name, roleId: role.id, permissions: role.permissions, actions: role.actions, scope: role.scope };
              }
              else modules[module.key] = { ...catalog.data!.presets[module.key][e.target.value], scope: "organization" };
              change(branch.id, { module_grants: modules });
            }}><option value="none">No access</option>{["viewer", "contributor", "editor", "manager", "admin"].map(role => <option key={role} value={role}>{role}</option>)}{catalog.data!.roles.filter(r => r.module_key === module.key).map(role => <option key={role.id} value={`custom:${role.id}`}>{role.name}</option>)}</select></label>;
          })}</div>}
        </>}
      </div>;
    })}
    <label className="grid gap-1 text-sm">Reason for branch role change<input aria-label="Branch role change reason" className="rounded border bg-background p-2" value={reason} onChange={e => setReason(e.target.value)} /></label>
    <AdminVerification value={verification} onChange={setVerification} />
    <Button type="button" disabled={busy || !draft || reason.trim().length < 5} onClick={async () => {
      setBusy(true); setMessage("");
      try {
        const { version, ...rest } = value;
        const proof = await administratorStepUp(verification);
        const saved = await api.put(`/branches/access/${userId}`, { ...rest, expected_version: version, reason }, { headers: { ...headers, "X-Access-Step-Up": proof.data.token } });
        setDraft(saved.data); setReason(""); setMessage("Branch memberships and roles saved. Changes apply immediately.");
      } catch (error: any) { setMessage(error.response?.data?.detail || "Unable to save branch roles"); }
      finally { setBusy(false); }
    }}>Save branch memberships & roles</Button>
    {message && <p role="status">{message}</p>}
  </section>;
}
