import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import EmbeddedSignup from "./EmbeddedSignup";
import { whatsappBase as base, whatsappError, type Status } from "./types";

export default function ConnectionPanel({ status, refresh }: { status: Status; refresh: () => Promise<void> }) {
  const [fields, setFields] = useState({ wabaId: "", phoneNumberId: "", accessToken: "", registrationPin: "" });
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState(""), [error, setError] = useState("");
  function report(message: string, failed = false) { setNotice(failed ? "" : message); setError(failed ? message : ""); }
  async function act(task: () => Promise<unknown>, message: string) {
    setBusy(true); report("");
    try { await task(); report(message); await refresh(); }
    catch (failure) { report(whatsappError(failure), true); await refresh(); }
    finally { setBusy(false); }
  }
  return <div className="space-y-5">
    {error && <p role="alert" className="rounded-lg border border-destructive/30 p-3 text-sm">{error}</p>}
    {notice && <p role="status" className="rounded-lg border border-emerald-600/30 p-3 text-sm">{notice}</p>}
    <div className="space-y-3 rounded-xl border p-4">
      <h3 className="font-medium">Connect your business account</h3>
      <p className="text-sm text-muted-foreground">Authorize your own WhatsApp Business Account through Meta. External customer signup requires Meta’s applicable Advanced Access approval.</p>
      <label className="block max-w-sm text-sm">Six-digit registration PIN, for a new number
        <Input type="password" inputMode="numeric" maxLength={6} autoComplete="new-password" value={fields.registrationPin} onChange={e => setFields({ ...fields, registrationPin: e.target.value })} />
      </label>
      <EmbeddedSignup enabled={status.onboardingConfigured} pin={fields.registrationPin} done={refresh} report={report} />
      {!status.onboardingConfigured && <p className="text-sm">Meta signup configuration is missing for this deployment.</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={busy} onClick={() => void act(() => api.post(base + "/connection/environment"), "Deployment account verified and connected")}>Use deployment account</Button>
        <Button variant="outline" disabled={busy || !status.connection} onClick={() => void act(() => api.post(base + "/connection/check"), "Account checked with Meta")}>Verify connection</Button>
        <Button variant="outline" disabled={busy || !status.configured} onClick={() => void act(() => api.post(base + "/connection/inbound-branch"), "New inbound conversations will route to the selected branch")}>Route inbox to selected branch</Button>
      </div>
      <p className="text-sm">{status.connection?.inboundBranchId ? `New inbound conversations route to branch ${status.connection.inboundBranchId}.` : "Choose a writable branch in the top bar, then configure inbox routing. Until then, incoming conversations are retained privately for an administrator to assign."} Existing conversations keep their branch.</p>
      <p className="break-all text-xs text-muted-foreground">Webhook: {window.location.origin}{status.webhookPath}</p>
    </div>
    <details className="rounded-xl border p-4">
      <summary className="cursor-pointer font-medium">Manual connection for an existing authorized account</summary>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm">WhatsApp Business Account ID<Input value={fields.wabaId} onChange={e => setFields({ ...fields, wabaId: e.target.value })} /></label>
        <label className="text-sm">Meta phone number ID<Input value={fields.phoneNumberId} onChange={e => setFields({ ...fields, phoneNumberId: e.target.value })} /></label>
        <label className="text-sm sm:col-span-2">Server access token<Input type="password" autoComplete="off" value={fields.accessToken} onChange={e => setFields({ ...fields, accessToken: e.target.value })} /></label>
        <Button disabled={busy || !fields.wabaId || !fields.phoneNumberId || !fields.accessToken} onClick={() => void act(async () => {
          await api.post(base + "/connection", { ...fields, registrationPin: fields.registrationPin || null });
          setFields({ wabaId: "", phoneNumberId: "", accessToken: "", registrationPin: "" });
        }, "Authorized account connected")}>Verify and connect account</Button>
      </div>
    </details>
    {status.connection?.status === "registration_required" && <Button disabled={busy || fields.registrationPin.length !== 6} onClick={() => void act(() => api.post(base + "/connection/register", { pin: fields.registrationPin }), "Phone registration checked")}>Register phone with Meta</Button>}
    {status.connection && status.connection.status !== "disconnected" && <Button variant="outline" disabled={busy} onClick={() => {
      if (window.confirm("Disconnect this organization’s WhatsApp account? Sending will stop. Conversation history will remain.")) void act(async () => {
        const result = (await api.delete<{ note?: string }>(base + "/connection")).data;
        if (result.note) throw new Error(result.note);
      }, "WhatsApp account disconnected");
    }}>Disconnect WhatsApp account</Button>}
  </div>;
}
