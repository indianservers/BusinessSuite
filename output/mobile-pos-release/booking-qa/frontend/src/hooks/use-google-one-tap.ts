import { useEffect, useRef } from "react";
import type { FirebaseOptions } from "firebase/app";

type GoogleIdentity = {
  initialize: (options: { client_id: string; auto_select: boolean; callback: (response: { credential: string }) => void }) => void;
  prompt: () => void;
  cancel: () => void;
};
let script: Promise<void> | undefined;
let attempted = false;
function identity() {
  return (window as Window & { google?: { accounts?: { id?: GoogleIdentity } } }).google?.accounts?.id;
}
function loadIdentity() {
  if (identity()) return Promise.resolve();
  if (!script) script = new Promise<void>((resolve, reject) => {
    const element = document.createElement("script");
    element.src = "https://accounts.google.com/gsi/client";
    element.async = true;
    element.onload = () => resolve();
    element.onerror = () => reject(new Error("Google One Tap unavailable"));
    document.head.appendChild(element);
  });
  return script;
}

/** Only Google's own prompt is rendered. A dismissed/unavailable prompt is never retried on this page. */
export function useGoogleOneTap<T>({ enabled, config, onSuccess, onError, onBusy }: {
  enabled: boolean; config?: FirebaseOptions; onSuccess: (data: T) => void; onError: (message: string) => void; onBusy: (busy: boolean) => void;
}) {
  const callbacks = useRef({ onSuccess, onError, onBusy });
  callbacks.current = { onSuccess, onError, onBusy };
  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_ONE_TAP_CLIENT_ID;
    if (!enabled || !config || !clientId || attempted) return;
    try { if (Date.now() - Number(sessionStorage.getItem("suite-one-tap-attempted")) < 86400000) return; } catch { /* Storage can be blocked. */ }
    let active = true;
    const cancel = () => identity()?.cancel();
    // Beginning another authentication method dismisses the ambient prompt.
    const stopForInput = (event: FocusEvent) => {
      if ((event.target as HTMLElement)?.closest("input, button")) cancel();
    };
    void loadIdentity().then(() => {
      if (!active || attempted) return;
      attempted = true;
      try { sessionStorage.setItem("suite-one-tap-attempted", String(Date.now())); } catch { /* In-memory guard still prevents repeats. */ }
      identity()?.initialize({ client_id: clientId, auto_select: false, callback: response => {
        if (!active) return;
        callbacks.current.onBusy(true);
        void import("@/services/firebaseLogin").then(({ googleCredentialLogin }) => googleCredentialLogin(config, response.credential))
          .then(result => { if (active) callbacks.current.onSuccess(result.data); })
          .catch(() => { if (active) callbacks.current.onError("Google One Tap could not complete. Use Continue with Google or your email below."); })
          .finally(() => callbacks.current.onBusy(false));
      } });
      identity()?.prompt();
      document.addEventListener("focusin", stopForInput);
    }).catch(() => { /* Standard sign-in remains available when GIS is blocked. */ });
    return () => { active = false; cancel(); document.removeEventListener("focusin", stopForInput); };
  }, [enabled, config]);
}
