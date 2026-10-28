import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { hub, request, send, setToken } from "./api";
import { PublicHeader } from "./ApplicationPage";

export type SavedApplication = {
  status: string; reference?: string; intern_id?: string; can_login: boolean;
  email: string; full_name: string; review_note?: string;
  details: Record<string, unknown>;
};
export type ApplicantProfile = {
  email: string; full_name: string; expires_at?: number;
  application?: SavedApplication | null;
};

export function ReturningApplicant({ record }: { record: SavedApplication }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mfa, setMfa] = useState("");
  const [method, setMethod] = useState("totp");
  const [code, setCode] = useState("");
  function openDashboard(result: any) {
    if (result.mfa_required) { setMfa(result.mfa_token); return; }
    if (!result.access_token) throw new Error("Sign-in could not be completed. Please retry.");
    setToken(result.access_token, result.refresh_token);
    window.location.assign("/");
  }
  async function login() {
    setBusy(true); setError("");
    try { openDashboard(await hub("/signup/login", send("POST"))); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (record.can_login) void login(); }, [record.email, record.can_login]);
  return <div className="application-page"><PublicHeader/><main className="status-layout"><section className="application-panel">
    <h1>You already submitted details</h1>
    <p>Your saved record has been found. You do not need to submit another application.</p>
    <div className="status-result" role="status">
      <span className={`badge ${record.status === "Approved" ? "green" : "orange"}`}>{record.status}</span>
      {record.reference && <p>Reference: <b>{record.reference}</b></p>}
      {record.intern_id && <p>Intern ID: <b>{record.intern_id}</b></p>}
      <p>{record.review_note || (record.status === "Pending" ? "Your application is awaiting review. Intern access becomes available after approval." : record.status === "Approved" ? record.can_login ? "Your application is approved. Opening your Interns Hub dashboard…" : "Your application is approved. Please contact the program team to activate your intern account." : record.status === "Correction Requested" ? "Please update the details requested by the review team." : record.status === "Rejected" ? "Your application was not approved. Contact the program team for further information." : "An account already exists for this email. Contact the program team for access.")}</p>
    </div>
    <details><summary>View your submitted details</summary><dl>
      {Object.entries({full_name:record.full_name,email:record.email,...record.details}).filter(([,value])=>value !== null && value !== "").map(([key,value])=><div key={key}><dt style={{textTransform:"capitalize"}}>{key.replaceAll("_"," ")}</dt><dd style={{overflowWrap:"anywhere"}}>{String(value)}</dd></div>)}
    </dl></details>
    {record.status === "Correction Requested" && <Link className="button" to="/apply?correction=1">Update requested details</Link>}
    {error && <p className="error" role="alert">{error}</p>}
    {mfa ? <form onSubmit={async event=>{event.preventDefault();setBusy(true);setError("");try{openDashboard(await request("/auth/mfa/verify",send("POST",{mfa_token:mfa,method,code})));}catch(failure){setError((failure as Error).message);}finally{setBusy(false);}}}>
      <label>Verification method<select value={method} onChange={event=>setMethod(event.target.value)}><option value="totp">Authenticator code</option><option value="recovery">Recovery code</option></select></label>
      <label>Verification code<input required autoComplete="one-time-code" value={code} onChange={event=>setCode(event.target.value)}/></label>
      <button className="button full" disabled={busy}>{busy?"Verifying…":"Verify & Open Dashboard"}</button>
    </form> : record.can_login && <button className="button full" disabled={busy} onClick={()=>void login()}>{busy?"Opening dashboard…":"Open Interns Hub Dashboard"}</button>}
    <p><Link to="/login">Go to intern login</Link></p>
  </section></main></div>;
}
