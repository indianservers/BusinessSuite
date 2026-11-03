import CompactForm from "@/components/forms/CompactForm";
import BranchLifecycleSettings from "./BranchLifecycleSettings";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import BranchOwnershipReview from "@/components/suite/BranchOwnershipReview";
import { useAuthStore } from "@/store/authStore";
import BranchMembershipSettings from "./BranchMembershipSettings";

type Branch = { id: number; name: string; code: string; is_active: boolean; can_write: boolean };
type Context = { manage_access: boolean; branches: Branch[] };

export default function BranchSettings() {
  const qc = useQueryClient();
  const user = useAuthStore(s => s.user);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const context = useQuery({ queryKey: ["settings-branches"], queryFn: () => api.get<Context>("/branches/context").then(r => r.data), staleTime: 0 });
  if (context.isPending) return <p role="status">Loading branches…</p>;
  if (context.isError) return <p role="alert">Unable to load branches. <button onClick={() => void context.refetch()}>Retry</button></p>;
  return <div className="settings-stack">
    <section className="settings-panel"><h2>Create a branch</h2>
      <p>Each branch has its own customers, sales and other business records. Creating a branch does not give existing users access automatically.</p>
      {context.data.manage_access ? <CompactForm onSubmit={async e => {
        e.preventDefault(); setSaving(true); setError(""); setMessage("");
        try {
          await api.post("/branches", { name: name.trim(), code: code.trim(), reason: reason.trim() });
          setMessage(`${name.trim()} created. Assign its users and module roles in Users & permissions.`);
          setName(""); setCode(""); setReason("");
          await qc.invalidateQueries({ predicate: q => q.queryKey.some(k => typeof k === "string" && /branch/.test(k)) });
        } catch (err: any) { setError(typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Could not create branch. Check the fields and try again."); }
        finally { setSaving(false); }
      }}>
        <div className="settings-form-grid">
          <label>Branch name<input required maxLength={150} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Chennai" /></label>
          <label>Branch code<input required maxLength={20} pattern="[A-Za-z0-9_\-]+" value={code} onChange={e => setCode(e.target.value)} placeholder="e.g. CHN" /><small>Unique within this company. Letters, numbers, underscores or hyphens.</small></label>
          <label>Reason for creating branch<input required minLength={5} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. New Chennai office" /></label>
        </div>
        <button className="settings-primary" disabled={saving || !name.trim() || reason.trim().length < 5}>{saving ? "Creating…" : "Create branch"}</button>
      </CompactForm> : <p>You need branch administration access to create branches.</p>}
      {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    </section>
    <BranchLifecycleSettings/>
    <section className="settings-panel"><h2>Next: assign users and permissions</h2><p>Choose a user, set their company module permissions, then select branches and a role for each module. For example: CRM manager in Chennai and Sales viewer in Bengaluru.</p><Link className="settings-primary" to="/settings/users">Manage users & permissions</Link></section>
    {context.data.manage_access && <BranchMembershipSettings branches={context.data.branches}/>}
    {user?.is_superuser && <section className="settings-panel"><BranchOwnershipReview branches={context.data.branches}/></section>}
  </div>;
}
