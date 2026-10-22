import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { workspaceError } from "@/apps/project-management/pages/workspaceTypes";

type Preview = { email: string; workspace: string; role: string; account_exists: boolean };
export default function WorkspaceInvitationPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [invitation, setInvitation] = useState<Preview>();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [activated, setActivated] = useState(false);
  const next = `/pms/invitation?token=${encodeURIComponent(token)}`;
  const signIn = `/pms/login?next=${encodeURIComponent(activated ? "/pms/workspaces" : next)}`;
  useEffect(() => {
    let active = true;
    api.get<Preview>("/project-management/workspace-invitations/preview", { params: { token } })
      .then(({ data }) => { if (active) setInvitation(data); })
      .catch(e => { if (active) setError(workspaceError(e)); });
    return () => { active = false; };
  }, [token]);
  async function accept() {
    setBusy(true); setError("");
    try {
      if (!invitation?.account_exists) {
        await api.post("/project-management/workspace-invitations/activate", { token, password });
        setPassword(""); setActivated(true);
      } else {
        const { data } = await api.post("/project-management/workspace-invitations/accept", { token });
        navigate(`/pms/workspaces?workspace=${data.workspace_id}`, { replace: true });
      }
    } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
  }
  return <main className="flex min-h-dvh items-center justify-center bg-slate-50 p-5">
    <section className="w-full max-w-md space-y-5 rounded-xl border bg-white p-7 shadow-sm">
      <h1 className="text-2xl font-semibold">Workspace invitation</h1>
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!invitation && !error && <p role="status">Loading invitation…</p>}
      {invitation && <>
        <p>Join <strong>{invitation.workspace}</strong> as <strong>{invitation.role}</strong>.</p>
        <p className="break-all text-sm text-slate-600">Invited email: {invitation.email}</p>
        {activated ? <div role="status"><p className="mb-4 text-green-700">Account activated. You are now a team member. Sign in to open your workspace.</p><Link className="text-violet-700 underline" to={signIn} onClick={() => logout()}>Sign in to your workspace</Link></div>
          : !invitation.account_exists ? <form className="space-y-4" onSubmit={e => { e.preventDefault(); void accept(); }}>
            <p className="text-sm text-slate-600">Create your account using the invited email. This link can be used once.</p>
            <label className="block text-sm">Create password<input className="mt-2 w-full rounded border p-3" type="password" autoComplete="new-password" required minLength={12} maxLength={72} value={password} onChange={e => setPassword(e.target.value)} /></label>
            <p className="text-xs text-slate-500">Use at least 12 characters.</p>
            <button className="w-full rounded bg-violet-600 p-3 text-white" disabled={busy}>{busy ? "Activating…" : "Activate account and join"}</button>
          </form> : user?.email.toLowerCase() === invitation.email.toLowerCase() ? <button className="w-full rounded bg-violet-600 p-3 text-white" disabled={busy} onClick={() => void accept()}>{busy ? "Joining…" : "Accept invitation"}</button>
            : <div><p className="mb-4 text-sm">Sign in with the invited email to accept.</p><Link className="text-violet-700 underline" to={signIn} onClick={() => logout()}>Sign in as {invitation.email}</Link></div>}
      </>}
      <Link className="block text-sm text-slate-500 underline" to="/">Back to Business Suite</Link>
    </section>
  </main>;
}
