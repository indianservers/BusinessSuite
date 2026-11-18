import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { syncScope } from "@/shared/record-sync/store";
import { Button } from "@/components/ui/button";
export type CreationResult = { title: string; href?: string; status?: string; next?: { label: string; href: string }[]; undo?: () => Promise<unknown>; scope?: string };
export function announceCreated(result: CreationResult) { window.dispatchEvent(new CustomEvent("suite:create-result", { detail: { ...result, scope: syncScope() } })); }
/** Only confirmed writes publish results. Undo is supplied only by reversible flows. */
export default function CreationOutcome() {
  const [result, setResult] = useState<CreationResult>(), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const navigate = useNavigate(), user = useAuthStore(s => s.user);
  const scope = syncScope();
  useEffect(() => { setResult(undefined); setBusy(false); setError(""); }, [scope]);
  useEffect(() => { const show = (event: Event) => { const next = (event as CustomEvent<CreationResult>).detail; if (next.scope !== syncScope()) return; setResult(next); setError(""); }; window.addEventListener("suite:create-result", show); return () => window.removeEventListener("suite:create-result", show); }, []);
  const safe = (href: string) => /^\/(?!\/)/.test(href) && canAccessRoute(href.split(/[?#]/)[0], user?.role, user?.is_superuser);
  if (!result || result.scope !== scope) return null;
  return <section className="suite-create-result" aria-label="Creation result"><p role="status"><strong>{result.title}</strong>{result.status && <span> · {result.status}</span>}</p><div className="flex flex-wrap gap-2">
    {result.href && safe(result.href) && <Button size="sm" variant="outline" disabled={busy} onClick={() => navigate(result.href!)}>Open</Button>}
    {result.next?.filter(action => safe(action.href)).map(action => <Button key={action.label} size="sm" variant="outline" disabled={busy} onClick={() => navigate(action.href)}>{action.label}</Button>)}
    {result.undo && <Button size="sm" variant="outline" disabled={busy} onClick={async () => { const captured = syncScope(); setBusy(true); setError(""); try { await result.undo!(); if (captured === syncScope()) setResult(undefined); } catch { if (captured === syncScope()) setError("Could not undo. The record is still saved; open it to review."); } finally { if (captured === syncScope()) setBusy(false); } }}>{busy ? "Undoing…" : "Undo"}</Button>}
    <Button size="sm" variant="ghost" disabled={busy} onClick={() => setResult(undefined)} aria-label="Dismiss creation result">Dismiss</Button></div>{error && <p role="alert">{error}</p>}</section>;
}
