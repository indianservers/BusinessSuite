import { useEffect, useState } from "react";
import { hub } from "./api";
import { firebaseConfig } from "./config";
import { useNavigate } from "react-router-dom";
import { setApplicationToken } from "./applicationSession";
import type { ApplicantProfile } from "./ReturningApplicant";

function ProviderMark({ provider }: { provider: string }) {
  return provider === "google" ? <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.8 12.2c0-.7-.1-1.5-.2-2.2H12v4.2h5.5a4.7 4.7 0 0 1-2 3.1v2.6h3.4c2-1.9 2.9-4.6 2.9-7.7Z"/><path fill="#34A853" d="M12 22c2.7 0 5-.9 6.9-2.1l-3.4-2.6c-.9.6-2.1 1-3.5 1-2.7 0-5-1.8-5.8-4.3H2.7v2.7A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.2 14a6 6 0 0 1 0-4V7.3H2.7a10 10 0 0 0 0 9.4L6.2 14Z"/><path fill="#EA4335" d="M12 5.7c1.5 0 2.8.5 3.9 1.5l2.9-2.9A10 10 0 0 0 2.7 7.3L6.2 10C7 7.5 9.3 5.7 12 5.7Z"/></svg> : <span className="microsoft-mark" aria-hidden="true"><i/><i/><i/><i/></span>;
}

export function SocialSignup({mode="signup",onVerified}:{mode?:"signup"|"continue";onVerified?:(profile:ApplicantProfile)=>void}) {
  const [providers, setProviders] = useState<Array<{ provider: string; enabled: boolean }> | null>(null);
  const [configurationError, setConfigurationError] = useState("");
  const [configurationAttempt, setConfigurationAttempt] = useState(0);
  const [busy,setBusy] = useState("");
  const [error,setError] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    setProviders(null);
    setConfigurationError("");
    hub("/signup/providers", { signal: controller.signal, cache: "no-store" }).then(result => {
      if (disposed) return;
      if (!firebaseConfig?.projectId || !firebaseConfig.apiKey || !firebaseConfig.authDomain || !firebaseConfig.appId) {
        setProviders([]);
        setConfigurationError("Google signup is not configured on this site. Please contact the program team.");
      } else if (result.project_id !== firebaseConfig.projectId) {
        setProviders([]);
        setConfigurationError("The signup service and this site use different Google configurations. Please contact the program team.");
      } else {
        const available = Array.isArray(result.providers) ? result.providers : [];
        setProviders(available);
        if (!available.some((item: {provider: string; enabled: boolean}) => item.provider === "google" && item.enabled)) {
          setConfigurationError("Google signup is currently unavailable. Please retry or contact the program team.");
        }
      }
    }).catch(() => {
      if (disposed) return;
      setProviders([]);
      setConfigurationError(controller.signal.aborted ? "Loading Google signup took too long. Please retry." : "Could not load Google signup. Check your connection and retry.");
    }).finally(() => window.clearTimeout(timeout));
    return () => { disposed = true; window.clearTimeout(timeout); controller.abort(); };
  }, [configurationAttempt]);
  async function signup(provider:string) {
    setBusy(provider);setError("");
    try {
      const {firebaseSignup} = await import("./firebaseSignup");
      const profile = await firebaseSignup();
      setApplicationToken(profile.application_token);
      if(onVerified) onVerified(profile);
      else navigate("/apply");
    } catch (failure:any) {
      const messages:Record<string,string>={
        "auth/popup-closed-by-user":"Sign-in was canceled. Sign in with Google to continue.",
        "auth/popup-blocked":"Please allow the sign-in popup, then try again.",
        "auth/unauthorized-domain":"Google sign-in is not available on this domain yet. Please contact the program team.",
        "auth/operation-not-allowed":"Google sign-in is temporarily unavailable. Please try again later.",
        "auth/account-exists-with-different-credential":"This account uses another sign-in method. Please contact the program team.",
      };
      setError(messages[failure.code] || "Google sign-in could not be completed. Please try again.");
    } finally {setBusy("");}
  }
  return <div className="social-signup">
    {mode === "signup" && <div className="signup-divider"><span>or start your application with</span></div>}
    <div className="social-signup-buttons">
      {["google"].map(provider => <button type="button" key={provider}
        className="social-signup-button" disabled={!!busy || !providers?.some(item => item.provider === provider && item.enabled)}
        onClick={() => {void signup(provider);}}>
        <ProviderMark provider={provider}/><span>{providers === null ? "Loading Google sign-in…" : busy === provider ? "Connecting…" : mode === "continue" ? "Sign in with Google" : "Sign up with Google"}</span>
      </button>)}
    </div>
    {providers === null && <p className="social-signup-note" role="status">Checking Google signup availability…</p>}
    {configurationError && <div className="social-signup-error" role="alert"><p>{configurationError}</p><button type="button" className="underline" onClick={() => setConfigurationAttempt(attempt => attempt + 1)}>Retry Google signup</button></div>}
    {error && <p className="social-signup-error" role="alert">{error}</p>}
  </div>;
}
