import { useEffect, useState } from "react";
import { hub } from "./api";
import { firebaseConfig } from "./config";
import { useNavigate } from "react-router-dom";

function ProviderMark({ provider }: { provider: string }) {
  return provider === "google" ? <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.8 12.2c0-.7-.1-1.5-.2-2.2H12v4.2h5.5a4.7 4.7 0 0 1-2 3.1v2.6h3.4c2-1.9 2.9-4.6 2.9-7.7Z"/><path fill="#34A853" d="M12 22c2.7 0 5-.9 6.9-2.1l-3.4-2.6c-.9.6-2.1 1-3.5 1-2.7 0-5-1.8-5.8-4.3H2.7v2.7A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.2 14a6 6 0 0 1 0-4V7.3H2.7a10 10 0 0 0 0 9.4L6.2 14Z"/><path fill="#EA4335" d="M12 5.7c1.5 0 2.8.5 3.9 1.5l2.9-2.9A10 10 0 0 0 2.7 7.3L6.2 10C7 7.5 9.3 5.7 12 5.7Z"/></svg> : <span className="microsoft-mark" aria-hidden="true"><i/><i/><i/><i/></span>;
}

export function SocialSignup() {
  const [providers, setProviders] = useState<Array<{ provider: string; enabled: boolean }> | null>(null);
  const [busy,setBusy] = useState("");
  const [error,setError] = useState("");
  const navigate = useNavigate();
  useEffect(() => { hub("/signup/providers").then(result=>setProviders(result.project_id === firebaseConfig?.projectId ? result.providers : [])).catch(() => setProviders([])); }, []);
  async function signup(provider:string) {
    setBusy(provider);setError("");
    try {
      const {firebaseSignup} = await import("./firebaseSignup");
      const profile = await firebaseSignup();
      navigate("/apply",{state:{signupProfile:profile}});
    } catch (failure:any) {
      const messages:Record<string,string>={
        "auth/popup-closed-by-user":"Signup was canceled. You can try again or apply with email.",
        "auth/popup-blocked":"Please allow the sign-in popup, then try again.",
        "auth/unauthorized-domain":"Social signup is not available on this domain yet. Please apply with email.",
        "auth/operation-not-allowed":"This signup provider is not available yet. Please apply with email.",
        "auth/account-exists-with-different-credential":"Use the provider you previously used with this email, or apply with email.",
      };
      setError(messages[failure.code] || "Social signup could not be completed. Please try again or apply with email.");
    } finally {setBusy("");}
  }
  return <div className="social-signup">
    <div className="signup-divider"><span>or start your application with</span></div>
    <div className="social-signup-buttons">
      {["google"].map(provider => <button type="button" key={provider}
        className="social-signup-button" disabled={!!busy || !providers?.some(item => item.provider === provider && item.enabled)}
        onClick={() => {void signup(provider);}}>
        <ProviderMark provider={provider}/><span>{busy === provider ? "Connecting…" : `Sign up with ${provider === "google" ? "Google" : "Microsoft"}`}</span>
      </button>)}
    </div>
    {providers && !providers.some(item => item.enabled) && <p className="social-signup-note">Google signup is being enabled. You can apply with email below.</p>}
    {error && <p className="social-signup-error" role="alert">{error}</p>}
  </div>;
}
