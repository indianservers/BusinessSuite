import { useEffect, useState } from "react";
import { useOperations } from "@/lib/async-progress";
export { beginProgress } from "@/lib/async-progress";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import "./async-progress.css";

export default function AsyncProgress() {
  const { active, result, error } = useOperations();
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!active.length) return; setNow(Date.now()); const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, [active]);
  if (!active.length && !result) return null;
  const operation = active[0];
  const seconds = operation ? Math.max(0, Math.floor((now - operation.started) / 1000)) : 0;
  const label = operation ? operation.label : result === "error" ? "Couldn’t finish — check the error message" : "Up to date";
  return <div className={`async-progress ${active.length ? "working" : result}`}>
    <div className="async-progress-line" role="progressbar" aria-label={label} {...(!active.length ? { "aria-valuenow": 100 } : {})}><i /></div>
    <div role="status" aria-live="polite" className="async-progress-card">
      {operation ? <Loader2 size={17} className="async-progress-spinner" /> : result === "error" ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
      <span>{label}<small>{operation ? seconds >= 8 ? "Still working. Keep this tab open." : "Waiting for server confirmation" : result === "error" ? error || "Review the message before trying again." : "Your changes are confirmed"}</small></span>
      {operation && <span className="async-progress-time">{active.length > 1 ? `${active.length} actions` : `${seconds}s`}</span>}
    </div>
  </div>;
}
