import { useEffect, useState } from "react";
import { GraduationCap, ShieldCheck } from "lucide-react";
import { ApplicationPage, PublicHeader } from "./ApplicationPage";
import { SocialSignup } from "./SocialSignup";
import { applicationToken, setApplicationToken } from "./applicationSession";
import { hub } from "./api";
import { useLocation } from "react-router-dom";
import { ReturningApplicant, type ApplicantProfile } from "./ReturningApplicant";

export function ApplicationGate() {
  const [profile,setProfile] = useState<ApplicantProfile | null>(null);
  const location = useLocation();
  const [checking,setChecking] = useState(!!applicationToken());
  useEffect(()=>{
    if(!profile?.expires_at) return;
    const timeout=setTimeout(()=>{setApplicationToken(null);setProfile(null);},Math.max(0,profile.expires_at*1000-Date.now()));
    return ()=>clearTimeout(timeout);
  },[profile]);
  useEffect(()=>{
    const expired=()=>{setApplicationToken(null);setProfile(null);setChecking(false);};
    window.addEventListener("internhub:applicant-expired",expired);
    return ()=>window.removeEventListener("internhub:applicant-expired",expired);
  },[]);
  useEffect(()=>{
    document.title = "Sign in to Apply · Interns Hub";
    if (!applicationToken()) return;
    let active=true;
    hub("/signup/session").then(result=>{if(active)setProfile(result);})
      .catch(()=>{if(active)setApplicationToken(null);}).finally(()=>{if(active)setChecking(false);});
    return ()=>{active=false;};
  },[]);
  function signOut() {setApplicationToken(null);setProfile(null);}
  if (profile) {
    const record = profile.application;
    const correcting = record?.status === "Correction Requested" && new URLSearchParams(location.search).get("correction") === "1";
    return <><div className="applicant-session-bar"><ShieldCheck size={17}/><span>Signed in with Google as <strong>{profile.email}</strong></span><button type="button" onClick={signOut}>Use another account</button></div>{record && !correcting ? <ReturningApplicant record={record}/> : <ApplicationPage key={profile.email} applicant={record ? {...profile,full_name:record.full_name,details:record.details} : profile}/>}</>;
  }
  return <div className="application-page"><PublicHeader/><main className="application-signin-layout"><section className="application-signin-card">
    <span className="application-signin-icon"><GraduationCap size={36}/></span>
    <span className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</span>
    <h1>Sign in with Google<br/>to continue</h1>
    <p>Use your Google account to open the internship application. We’ll fill in your name and email so you can get started.</p>
    {checking ? <p role="status">Checking your Google sign-in…</p> : <SocialSignup mode="continue" onVerified={setProfile}/>}
    <div className="application-signin-assurance"><ShieldCheck size={18}/><span>Your application is reviewed by our team before intern access is activated.</span></div>
  </section></main></div>;
}
