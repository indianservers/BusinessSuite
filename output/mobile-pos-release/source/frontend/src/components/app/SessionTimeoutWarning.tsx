import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";

const IDLE_MS = 25 * 60 * 1000;
const WARNING_MS = 60 * 1000;

export default function SessionTimeoutWarning() {
  const { isAuthenticated, logout } = useAuthStore();
  const [deadline, setDeadline] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(WARNING_MS / 1000);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    const reset = () => {
      setDeadline(null);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setDeadline(Date.now() + WARNING_MS), IDLE_MS - WARNING_MS);
    };
    ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach((name) => window.addEventListener(name, reset, { passive: true }));
    reset();
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
      ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach((name) => window.removeEventListener(name, reset));
    };
  }, [isAuthenticated]);

  useEffect(() => {
    if (!deadline) return;
    const interval = window.setInterval(() => {
      const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setRemaining(seconds);
      if (seconds <= 0) logout();
    }, 250);
    return () => window.clearInterval(interval);
  }, [deadline, logout]);

  if (!deadline) return null;
  return (
    <div className="fixed inset-x-0 top-4 z-50 mx-auto w-[min(92vw,440px)] rounded-lg border bg-background p-4 shadow-xl">
      <p className="font-semibold">Session timeout warning</p>
      <p className="mt-1 text-sm text-muted-foreground">You will be logged out in {remaining}s due to inactivity.</p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" onClick={logout}>Logout now</Button>
        <Button onClick={() => setDeadline(null)}>Stay signed in</Button>
      </div>
    </div>
  );
}
