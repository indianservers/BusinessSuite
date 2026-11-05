import { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { whatsappBase as base, whatsappError } from "./types";

type Signup = { state: string; appId: string; configId: string; apiVersion: string };
type Facebook = {
  init: (options: Record<string, unknown>) => void;
  login: (callback: (response: { authResponse?: { code?: string } }) => void, options: Record<string, unknown>) => void;
};
async function loadSDK(): Promise<Facebook> {
  const fb = () => (window as unknown as { FB?: Facebook }).FB;
  // sdk.js exposes a buffering placeholder before fbAsyncInit. Capturing it
  // makes later login() calls queue forever instead of opening a popup.
  const ready = () => fb() && !("__buffer" in fb()!);
  if (ready()) return fb()!;
  await new Promise<void>((resolve, reject) => {
    const host = window as unknown as { fbAsyncInit?: () => void };
    const previous = host.fbAsyncInit;
    let script = document.getElementById("business-suite-facebook-sdk") as HTMLScriptElement | null;
    const timeout = window.setTimeout(() => reject(new Error("Meta SDK could not load. Refresh and try again.")), 15000);
    const loaded = () => { if (ready()) { window.clearTimeout(timeout); resolve(); } };
    host.fbAsyncInit = () => { try { previous?.(); } finally { loaded(); } };
    if (!script) {
      script = document.createElement("script");
      script.id = "business-suite-facebook-sdk";
      script.src = "https://connect.facebook.net/en_US/sdk.js";
      script.async = true;
      script.crossOrigin = "anonymous";
    }
    script.addEventListener("load", loaded, { once: true });
    script.addEventListener("error", () => { window.clearTimeout(timeout); reject(new Error("Meta SDK could not load")); }, { once: true });
    if (!script.isConnected) document.body.appendChild(script);
    loaded();
  });
  if (!fb()) throw new Error("Meta SDK is unavailable");
  return fb()!;
}

export default function EmbeddedSignup({ enabled, pin, done, report }: {
  enabled: boolean; pin: string; done: () => Promise<void>; report: (message: string, error?: boolean) => void;
}) {
  const [session, setSession] = useState<Signup | null>(null);
  const [fb, setFB] = useState<Facebook | null>(null);
  const [busy, setBusy] = useState(false);
  const active = useRef<string | null>(null);
  const flow = useRef<{ code?: string; wabaId?: string; phoneNumberId?: string; completing?: boolean; pin?: string }>({});
  async function complete() {
    const value = flow.current;
    if (!session || active.current !== session.state || !value.code || !value.wabaId || !value.phoneNumberId || value.completing) return;
    value.completing = true;
    try {
      await api.post(base + "/onboarding/complete", { state: session.state, code: value.code, wabaId: value.wabaId, phoneNumberId: value.phoneNumberId, registrationPin: value.pin || null });
      report("Account connected. Check the sender status before sending.");
      await done();
    } catch (error) { report(whatsappError(error), true); }
    finally { active.current = null; flow.current = {}; setSession(null); setBusy(false); }
  }
  useEffect(() => {
    if (!session) return;
    function receive(event: MessageEvent) {
      if (event.origin !== "https://www.facebook.com") return;
      try {
        const value = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        if (value?.type !== "WA_EMBEDDED_SIGNUP") return;
        if (value.event === "FINISH" || value.event === "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING") {
          flow.current.wabaId = String(value.data?.waba_id || "");
          flow.current.phoneNumberId = String(value.data?.phone_number_id || "");
          void complete();
        } else if (value.event === "CANCEL" || value.event === "ERROR") {
          if (flow.current.completing) return;
          active.current = null; flow.current = {}; setBusy(false); setSession(null);
          report("Meta signup did not finish. Prepare a new connection to try again.", true);
        }
      } catch { /* Unrelated window messages are ignored. */ }
    }
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [session]);
  async function prepare() {
    setBusy(true);
    try {
      const next = (await api.post<Signup>(base + "/onboarding/start")).data;
      const sdk = await loadSDK();
      // Login for Business configurations are not supported by FedCM yet.
      sdk.init({ appId: next.appId, version: next.apiVersion, cookie: true, xfbml: false, fedCM: false });
      flow.current = { pin };
      active.current = next.state;
      setFB(sdk); setSession(next);
      report("Ready. Continue to Meta to authorize your business account. This signup session lasts ten minutes.");
    } catch (error) { report(whatsappError(error), true); }
    finally { setBusy(false); }
  }
  function launch() {
    if (!session || !fb) return;
    if (active.current !== session.state) return;
    setBusy(true);
    report("Complete the Meta popup. If it does not appear, check your browser's popup blocker or cancel and try again.");
    // Kept synchronous with the second user click so browsers permit the popup.
    try { fb.login(response => {
      if (active.current !== session.state) return;
      if (response.authResponse?.code) { flow.current.code = response.authResponse.code; void complete(); }
      else { active.current = null; flow.current = {}; setSession(null); setBusy(false); report("Meta did not return an authorization code. Start a new connection.", true); }
    }, { config_id: session.configId, response_type: "code", override_default_response_type: true, extras: { version: "v4" } });
    } catch { active.current = null; flow.current = {}; setSession(null); setBusy(false); report("Meta could not open. Check popup permissions, then start a new connection.", true); }
  }
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => {
      if (active.current !== session.state || flow.current.completing) return;
      active.current = null; flow.current = {}; setSession(null); setBusy(false);
      report("The Meta signup session expired. Start a new connection.", true);
    }, 10 * 60 * 1000);
    return () => window.clearTimeout(timer);
  }, [session]);
  useEffect(() => () => { active.current = null; flow.current = {}; }, []);
  return <div className="flex flex-wrap gap-2">
    <Button disabled={!enabled || busy} onClick={() => session ? launch() : void prepare()}>{busy ? "Waiting for Meta…" : session ? "Continue to Meta" : "Connect with Meta"}</Button>
    {session && <Button variant="outline" disabled={flow.current.completing} onClick={() => { active.current = null; setSession(null); setBusy(false); flow.current = {}; }}>Cancel signup</Button>}
  </div>;
}
