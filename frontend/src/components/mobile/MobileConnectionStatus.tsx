import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Wifi, WifiOff, X } from "lucide-react";

export default function MobileConnectionStatus() {
  const [online, setOnline] = useState(navigator.onLine), [reconnected, setReconnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const queries = useQueryClient();
  useEffect(() => {
    const offline = () => { setOnline(false); setReconnected(false); };
    const connected = () => { setOnline(true); setReconnected(true); };
    window.addEventListener("offline", offline); window.addEventListener("online", connected);
    return () => { window.removeEventListener("offline", offline); window.removeEventListener("online", connected); };
  }, []);
  if (online && !reconnected) return null;
  return <div className="mobile-connection-status" role="status">
    {online ? <Wifi size={18} aria-hidden="true" /> : <WifiOff size={18} aria-hidden="true" />}
    <span><strong>{online ? "Back online" : "You’re offline"}</strong><small>{online ? "Refresh to check the latest records." : "Keep this page open. Saving needs a connection."}</small></span>
    {online && <><button type="button" disabled={busy} onClick={async () => { setBusy(true); try { await queries.refetchQueries({ type: "active", stale: true }); setReconnected(false); } finally { setBusy(false); } }}>{busy ? "Refreshing…" : "Refresh"}</button><button type="button" aria-label="Dismiss connection status" onClick={() => setReconnected(false)}><X size={16} /></button></>}
  </div>;
}
