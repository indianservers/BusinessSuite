import AdminVerification, { administratorStepUp } from "./AdminVerification";
import { useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

export default function SuperAdminManager({ companyId }: { companyId: number }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return <><Button variant="outline" onClick={() => { setOpen(true); setMessage(""); }}>Add Super Admin</Button>
    <Dialog open={open} onOpenChange={value => { if (!busy) { setOpen(value); setPassword(""); setNewPassword(""); } }}>
      <DialogContent><DialogTitle>Add Super Admin</DialogTitle>
        <p className="text-sm text-muted-foreground">Grants full access to every installed module, users, and company settings. Enter an existing account email, or provide a password to create a new account.</p>
        <form className="space-y-4" onSubmit={async event => {
          event.preventDefault(); setBusy(true); setError(""); setMessage("");
          try {
            const token = (await administratorStepUp(password)).data.token;
            await api.post("/access/control/super-admins", { companyId, email: email.trim(), password: newPassword || null, reason }, { headers: { "X-Access-Step-Up": token } });
            setMessage(`Super Admin access granted to ${email.trim()}.`); setEmail(""); setReason("");
          } catch (e: any) { setError(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not grant access. Check the details and try again."); }
          finally { setBusy(false); setPassword(""); setNewPassword(""); }
        }}>
          <label className="block">Email<input className="w-full rounded border p-2" type="email" required value={email} onChange={e => setEmail(e.target.value)} /></label>
          <label className="block">New account password (leave empty for existing users)<input className="w-full rounded border p-2" type="password" autoComplete="new-password" value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label>
          <label className="block">Reason<input className="w-full rounded border p-2" required minLength={3} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
          <AdminVerification value={password} onChange={setPassword} />
          {error && <p role="alert" className="text-destructive">{error}</p>}{message && <p role="status">{message}</p>}
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Grant full Super Admin access"}</Button>
        </form>
      </DialogContent>
    </Dialog></>;
}
