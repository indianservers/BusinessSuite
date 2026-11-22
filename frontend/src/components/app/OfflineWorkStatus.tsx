import { useEffect, useState } from "react";
import { useRecordScope } from "@/lib/record-scope";
import { discardOfflineChange, offlineChangeEvent, offlineChanges } from "@/lib/offline-work";

export default function OfflineWorkStatus() {
  const scope = useRecordScope();
  const [changes, setChanges] = useState<Awaited<ReturnType<typeof offlineChanges>>>([]);
  const [problem, setProblem] = useState("");
  useEffect(() => {
    let active = true;
    let generation = 0;
    setChanges([]);
    setProblem("");
    const refresh = () => {
      const latest = ++generation;
      void offlineChanges().then(rows => {
        if (active && latest === generation) setChanges(rows.filter(row => !row.confirmed));
      }).catch(() => undefined);
    };
    refresh();
    window.addEventListener(offlineChangeEvent, refresh);
    return () => { active = false; window.removeEventListener(offlineChangeEvent, refresh); };
  }, [scope]);
  if (!changes.length) return null;
  const errors = changes.filter(change => change.error);
  return <details className="fixed bottom-20 right-4 z-40 max-w-[min(28rem,90vw)] rounded-lg border bg-background p-3 text-sm shadow">
    <summary aria-live="polite">{changes.length - errors.length} saved on this device{errors.length > 0 && ` · ${errors.length} need review`}</summary>
    <ul className="mt-2 max-h-64 space-y-2 overflow-auto">
      {changes.map(change => <li key={change.id}>
        <strong>{String(change.row.title || change.row.name || change.target)}</strong>
        <p>{change.error || "Waiting to sync"}</p>
        {change.error && <button type="button" className="underline" onClick={() => {
          if (window.confirm("Discard this saved device change?")) void discardOfflineChange(change.id).catch(() => setProblem("The change could not be discarded."));
        }}>Discard local change</button>}
      </li>)}
    </ul>
    {problem && <p role="alert">{problem}</p>}
  </details>;
}
