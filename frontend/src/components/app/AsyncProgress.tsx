import { useEffect, useState } from "react";
import { useOperations } from "../../lib/async-progress";
export { beginProgress } from "../../lib/async-progress";
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
  const percent = operation ? Math.min(95, Math.round(10 + 85 * (1 - Math.exp(-seconds / 9)))) : result === "error" ? undefined : 100;
  return <div className={`async-progress ${active.length ? "working" : result}`}>
    <div className="async-progress-line" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-valuetext={operation ? `${percent}% estimated` : label}><i style={{ width: `${percent ?? 95}%` }} /></div>
    <div role="status" aria-live="polite" className="async-progress-card">
      {operation ? <Loader2 size={17} className="async-progress-spinner" /> : result === "error" ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
      <span>{label}<small>{operation ? seconds >= 8 ? "Still working. Keep this tab open." : "Loading progress is estimated" : result === "error" ? error || "Review the message before trying again." : "Loading complete"}</small></span>
      <span className="async-progress-time">{percent === undefined ? "Failed" : `${percent}%`}</span>
    </div>
  </div>;
}
