import { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { whatsappBase as base, whatsappError } from "./types";

type Signup = { state: string; appId: string; configId: string; apiVersion: string; expires: number };
export default function EmbeddedSignup({ enabled, pin, done, report }: {
  enabled: boolean; pin: string; done: () => Promise<void>; report: (message: string, error?: boolean) => void;
}) {
  const [session, setSession] = useState<Signup | null>(null);
  const [busy, setBusy] = useState(false);
  const active = useRef<string | null>(null);
  const popup = useRef<Window | null>(null);
  const flow = useRef<{ completing?: boolean; pin?: string }>({});
  function clear() { active.current = null; flow.current = {}; setSession(null); setBusy(false); }
  useEffect(() => {
    if (!session) return;
    async function receive(event: MessageEvent) {
      if (event.origin !== window.location.origin || event.source !== popup.current || active.current !== session!.state) return;
      const value = event.data;
      if (value?.type !== "SUITE_WHATSAPP_AUTH" || value.state !== session!.state || flow.current.completing) return;
      if (typeof value.code !== "string" || value.code.length < 5 || value.code.length > 10000 || !/^\d{5,40}$/.test(value.wabaId) || !/^\d{5,40}$/.test(value.phoneNumberId)) return;
      flow.current.completing = true;
      let success = false;
      try {
        report("Meta authorization received. Verifying the sender and saving this organization's connection…");
        await api.post(base + "/onboarding/complete", { state: session!.state, code: value.code, wabaId: value.wabaId, phoneNumberId: value.phoneNumberId, registrationPin: flow.current.pin || null }, { timeout: 120000 });
        success = true;
        report("Account connected. Check the sender status before sending.");
        await done();
      } catch (error) { report(whatsappError(error), true); }
      finally {
        popup.current?.postMessage({ type: "SUITE_WHATSAPP_RESULT", state: session!.state, success }, window.location.origin);
        clear();
      }
    }
    window.addEventListener("message", receive);
    const timer = window.setTimeout(() => {
      if (active.current !== session.state || flow.current.completing) return;
      clear(); report("The Meta signup session expired. Start a new connection.", true);
    }, Math.max(0, session.expires - Date.now()));
    return () => { window.removeEventListener("message", receive); window.clearTimeout(timer); };
  }, [session]);
  useEffect(() => () => { active.current = null; flow.current = {}; }, []);
  async function prepare() {
    setBusy(true);
    try {
      if (pin && !/^\d{6}$/.test(pin)) throw new Error("Use a six-digit registration PIN, or leave it blank for an existing number.");
      const started = Date.now();
      const next = (await api.post<Omit<Signup, "expires">>(base + "/onboarding/start")).data;
      flow.current = { pin }; active.current = next.state;
      setSession({ ...next, expires: started + 10 * 60 * 1000 });
      report("Ready. Continue to Meta to authorize your business account. This signup session lasts ten minutes.");
    } catch (error) { report(whatsappError(error), true); }
    finally { setBusy(false); }
  }
  function launch() {
    if (!session || active.current !== session.state) return;
    // Synchronous user gesture. The dedicated page owns Meta's SDK lifecycle;
    // this authenticated workspace alone exchanges and saves the returned code.
    popup.current = window.open("/whatsapp-connect.html#" + encodeURIComponent(JSON.stringify(session)), "_blank");
    if (!popup.current) { report("Allow popups, then Continue to Meta again.", true); return; }
    popup.current.focus(); setBusy(true);
    report("Complete Meta authorization in the connection window, then return here.");
  }
  return <div className="flex flex-wrap gap-2">
    <Button disabled={!enabled || busy} onClick={() => session ? launch() : void prepare()}>{busy ? "Waiting for Meta…" : session ? "Continue to Meta" : "Connect with Meta"}</Button>
    {session && <Button variant="outline" disabled={flow.current.completing} onClick={() => { clear(); report("Signup cancelled. Your existing connection was kept."); }}>Cancel signup</Button>}
  </div>;
}
