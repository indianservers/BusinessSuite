import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";

export function useNotificationSnooze() {
  const user = useAuthStore(state => state.user);
  const key = `suite-notification-snooze:${user?.id}:${user?.access?.companyId}`;
  const read = (): Record<string, number> => {
    try { const value = JSON.parse(localStorage.getItem(key) || "{}"); return Object.fromEntries(Object.entries(value).filter((entry): entry is [string, number] => typeof entry[1] === "number" && entry[1] > Date.now())); } catch { return {}; }
  };
  const [state, setState] = useState(() => ({ key, values: read() }));
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer); }, []);
  const values = state.key === key ? state.values : read();
  const change = (id: number, until?: number) => {
    const next = { ...values };
    if (until) next[id] = until; else delete next[id];
    setState({ key, values: next });
    try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* The active session still supports snoozing. */ }
  };
  return { isSnoozed: (id: number) => (values[id] || 0) > now, snooze: (id: number) => change(id, Date.now() + 60 * 60 * 1000), restore: (id: number) => change(id) };
}
