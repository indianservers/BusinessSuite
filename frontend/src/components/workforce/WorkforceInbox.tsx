import { useEffect, useState } from "react";
import "./workforce.css";

export type WorkforceNotice = { id: number; kind: string; title: string; message: string; severity: string;
  created_at: string; acknowledged_at?: string; resolved_at?: string; resolution?: string };
export type WorkforceInboxResult = { items: WorkforceNotice[]; total: number; unacknowledged: number };
type Props = { load: (page: number) => Promise<WorkforceInboxResult>; acknowledge: (id: number) => Promise<unknown> };

export default function WorkforceInbox({ load, acknowledge }: Props) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<WorkforceInboxResult>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setError("");
    load(page).then(value => { if (active) setData(value); }).catch(error => { if (active) setError(error.message || "Could not load notices"); });
    return () => { active = false; };
  }, [page, load, revision]);
  return <div className="wf-space">
    <header><p className="wf-eyebrow">YOUR UPDATES</p><h1>Notices & warnings</h1>
      <p>Read messages from your supervisors and acknowledge receipt. Acknowledgement confirms you have read the message.</p></header>
    {error && <p role="alert" className="wf-error">{error}</p>}
    {!data && !error && <p role="status">Loading notices…</p>}
    {data && <p role="status">{data.unacknowledged} awaiting acknowledgement · {data.total} messages</p>}
    {data?.items.map(message => <article key={message.id} className={`wf-card wf-notice ${message.kind === "warning" ? "wf-warning" : ""}`}>
      <div className="wf-row"><strong>{message.kind === "warning" ? "Warning" : "Notice"} · {message.severity}</strong>
        <time>{new Date(message.created_at).toLocaleString()}</time></div>
      <h2>{message.title}</h2><p className="wf-message">{message.message}</p>
      {message.resolved_at && <p className="wf-success">Resolved: {message.resolution}</p>}
      {message.acknowledged_at ? <p>Acknowledged {new Date(message.acknowledged_at).toLocaleString()}</p> :
        <button disabled={busy !== null} onClick={async () => {
          setBusy(message.id); setError("");
          try { await acknowledge(message.id); setRevision(v => v + 1); window.dispatchEvent(new Event("workforce:acknowledged")); }
          catch (error: any) { setError(error.response?.data?.detail || error.message || "Could not acknowledge notice"); }
          finally { setBusy(null); }
        }}>{busy === message.id ? "Saving…" : "I have read this message"}</button>}
    </article>)}
    {data?.total === 0 && <div className="wf-card"><h2>You’re up to date</h2><p>Your supervisor’s notices and warnings will appear here.</p></div>}
    <footer className="wf-row"><button disabled={page === 1 || busy !== null} onClick={() => setPage(p => p - 1)}>Previous</button>
      <span>Page {page}</span><button disabled={!data || page * 25 >= data.total || busy !== null} onClick={() => setPage(p => p + 1)}>Next</button></footer>
  </div>;
}
