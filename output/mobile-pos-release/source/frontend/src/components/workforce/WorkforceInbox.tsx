import {useMobile} from "@/components/mobile/useMobile";
import { useEffect, useRef, useState } from "react";
import { useMobileContext } from "@/components/mobile/useMobileContext";
import { syncScope } from "@/shared/record-sync/store";
import "./workforce.css";
import "./workforce-inbox-mobile.css";

export type WorkforceNotice = { id: number; kind: string; title: string; message: string; severity: string;
  created_at: string; acknowledged_at?: string; resolved_at?: string; resolution?: string };
export type WorkforceInboxResult = { items: WorkforceNotice[]; total: number; unacknowledged: number };
type Props = { load: (page: number) => Promise<WorkforceInboxResult>; acknowledge: (id: number) => Promise<unknown> };

export default function WorkforceInbox({ load, acknowledge }: Props) {
  const scope = useMobileContext();
  return <InboxContents key={scope} load={load} acknowledge={acknowledge} />;
}

function InboxContents({ load, acknowledge }: Props) {
  const phone=useMobile(480);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [loading,setLoading]=useState(true);
  const [dataPage,setDataPage]=useState(1);
  const [loadFailed,setLoadFailed]=useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<WorkforceInboxResult>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  const acknowledgementPending = useRef(false);
  const [confirmed, setConfirmed] = useState<number[]>([]);
  useEffect(() => {
    let active = true;
    const scope = syncScope(), owned = phone;
    const current = () => active && (!owned || scope === syncScope());
    setError("");setLoading(true);setLoadFailed(false);
    load(page).then(value => { if (current()) {setData(value);setDataPage(page);} }).catch(error => { if (current()) {setError(error.message || "Could not load notices");setLoadFailed(true);} }).finally(()=>{if(current())setLoading(false);});
    return () => { active = false; };
  }, [page, load, revision]);
  const visibleData=phone && dataPage!==page ? undefined : data;
  return <div className="wf-space wf-inbox">
    <header><p className="wf-eyebrow">YOUR UPDATES</p><h1>Notices & warnings</h1>
      <p>Read messages from your supervisors and acknowledge receipt. Acknowledgement confirms you have read the message.</p></header>
    {error && <p role="alert" className="wf-error">{error}</p>}
    {phone && loadFailed && <button disabled={loading || busy!==null} onClick={()=>setRevision(v=>v+1)}>Retry notices</button>}
    {phone ? loading && <p role="status">{visibleData ? "Refreshing notices…" : "Loading notices…"}</p> : !data && !error && <p role="status">Loading notices…</p>}
    {visibleData && <p role="status">{visibleData.unacknowledged} awaiting acknowledgement · {visibleData.total} messages</p>}
    {visibleData?.items.map(message => <article key={message.id} className={`wf-card wf-notice ${message.kind === "warning" ? "wf-warning" : ""}`}>
      <div className="wf-row"><strong>{message.kind === "warning" ? "Warning" : "Notice"} · {message.severity}</strong>
        <time>{new Date(message.created_at).toLocaleString()}</time></div>
      <h2>{message.title}</h2><p className="wf-message">{message.message}</p>
      {message.resolved_at && <p className="wf-success">Resolved: {message.resolution}</p>}
      {message.acknowledged_at ? <p>Acknowledged {new Date(message.acknowledged_at).toLocaleString()}</p> : phone && confirmed.includes(message.id) ? <p role="status">Receipt confirmed</p> :
        <button disabled={busy !== null || phone && loading} onClick={async () => {
          if (phone && (acknowledgementPending.current || loading || confirmed.includes(message.id))) return;
          if (phone) acknowledgementPending.current = true;
          const scope = syncScope(), owned = phone;
          const current = () => !owned || mounted.current && scope === syncScope();
          setBusy(message.id); setError("");
          try { await acknowledge(message.id); if (!current()) return; if (owned) setConfirmed(ids => [...ids, message.id]); setRevision(v => v + 1); window.dispatchEvent(new Event("workforce:acknowledged")); }
          catch (error: any) { if (current()) setError(error.response?.data?.detail || error.message || "Could not acknowledge notice"); }
          finally { acknowledgementPending.current = false; if (current()) setBusy(null); }
        }}>{busy === message.id ? "Saving…" : "I have read this message"}</button>}
    </article>)}
    {visibleData?.total === 0 && <div className="wf-card"><h2>You’re up to date</h2><p>Your supervisor’s notices and warnings will appear here.</p></div>}
    <footer className="wf-row"><button disabled={page === 1 || busy !== null || phone && loading} onClick={() => setPage(p => p - 1)}>Previous</button>
      <span>Page {page}</span><button disabled={!visibleData || page * 25 >= visibleData.total || busy !== null || phone && loading} onClick={() => setPage(p => p + 1)}>Next</button></footer>
  </div>;
}
