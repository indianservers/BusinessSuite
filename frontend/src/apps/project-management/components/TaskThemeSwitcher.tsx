import { useSyncExternalStore } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
export type TaskTheme = "classic" | "whatsapp";
const event = "pms-task-theme";
function subscribe(callback: () => void) {
  window.addEventListener(event, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(event, callback);
    window.removeEventListener("storage", callback);
  };
}
export function useTaskTheme() {
  const user = useAuthStore((s) => s.user);
  const key = `pms-task-theme:${user?.id ?? "anonymous"}`;
  const [params, setParams] = useSearchParams();
  const stored = useSyncExternalStore(
    subscribe,
    () => {
      try {
        return localStorage.getItem(key) === "whatsapp"
          ? "whatsapp"
          : "classic";
      } catch {
        return "classic";
      }
    },
    () => "classic",
  );
  const override = params.get("theme");
  const theme: TaskTheme =
    override === "classic" || override === "whatsapp"
      ? override
      : stored === "whatsapp"
        ? "whatsapp"
        : "classic";
  const change = (value: TaskTheme) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* URL remains usable without storage. */
    }
    window.dispatchEvent(new Event(event));
    const next = new URLSearchParams(params);
    next.set("theme", value);
    setParams(next);
  };
  return { theme, change };
}
export default function TaskThemeSwitcher() {
  const { theme, change } = useTaskTheme();
  return (
    <div
      aria-label="Task appearance"
      role="group"
      className="task-theme-switch"
      style={{
        display: "inline-flex",
        gap: 2,
        padding: 3,
        border: "1px solid var(--border, #dce3e1)",
        borderRadius: 9,
        flexShrink: 0,
      }}
    >
      {(
        [
          ["classic", "Classic"],
          ["whatsapp", "WhatsApp style"],
        ] as const
      ).map(([value, label]) => (
        <button
          key={value}
          type="button"
          aria-pressed={theme === value}
          onClick={() => change(value)}
          style={{
            border: 0,
            borderRadius: 6,
            padding: "7px 10px",
            fontSize: 12,
            fontWeight: 600,
            whiteSpace: "nowrap",
            cursor: "pointer",
            background: theme === value ? "#d9f5e8" : "transparent",
            color: theme === value ? "#006c49" : "inherit",
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
