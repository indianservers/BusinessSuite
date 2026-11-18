import { useRef } from "react";
import { useSearchParams } from "react-router-dom";
import LoginPage from "@/pages/auth/LoginPage";
import SignupPage from "@/pages/auth/SignupPage";
export default function HomeAuthPanel({ signup, onChange }: { signup: boolean; onChange: (signup: boolean) => void }) {
  const [, setParams] = useSearchParams();
  const loginTab = useRef<HTMLButtonElement>(null), signupTab = useRef<HTMLButtonElement>(null);
  return <aside id="home-auth" className="home-auth" aria-label="Workspace access"><div className="home-auth-tabs" role="tablist" aria-label="Workspace access" onKeyDown={e => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) { e.preventDefault(); const next = e.key === "Home" ? false : e.key === "End" ? true : !signup; onChange(next); (next ? signupTab : loginTab).current?.focus(); }
  }}><button ref={loginTab} id="home-login-tab" role="tab" aria-selected={!signup} aria-controls="home-auth-content" tabIndex={signup ? -1 : 0} onClick={() => onChange(false)}>Log in</button><button ref={signupTab} id="home-signup-tab" role="tab" aria-selected={signup} aria-controls="home-auth-content" tabIndex={signup ? 0 : -1} onClick={() => onChange(true)}>Sign up</button></div><div id="home-auth-content" role="tabpanel" aria-labelledby={signup ? "home-signup-tab" : "home-login-tab"} onClick={event => {
    const link = (event.target as HTMLElement).closest("a");
    if (link && !link.target) {
      const url = new URL(link.href, location.origin);
      if (url.origin === location.origin && url.pathname === "/login") {
        event.preventDefault();
        setParams(old => { const next = new URLSearchParams(old); next.delete("auth"); if (url.searchParams.has("application")) next.set("application", "1"); return next; }, { replace: true });
      }
    }
  }}>{signup ? <SignupPage embedded/> : <LoginPage embedded onSignup={() => onChange(true)}/>}</div></aside>;
}
