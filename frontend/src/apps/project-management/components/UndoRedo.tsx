import { useCallback, useEffect, useState } from "react";
import { Undo2, Redo2 } from "lucide-react";
import { api } from "@/services/api";

export default function UndoRedo({
  workspaceId,
  refreshKey,
  onChanged,
  onError,
}: {
  workspaceId: number;
  refreshKey?: unknown;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [available, setAvailable] = useState({ undo: false, redo: false });
  const [busy, setBusy] = useState(false);
  const base = `/project-management/workspaces/${workspaceId}/recovery`;
  const reload = useCallback(async () => {
    try {
      const { data } = await api.get<{ state: string }[]>(`${base}/history`, {
        progress: false,
      });
      setAvailable({
        undo: data.some((row) => row.state === "applied"),
        redo: data.some((row) => row.state === "undone"),
      });
    } catch {
      setAvailable({ undo: false, redo: false });
    }
  }, [base]);
  useEffect(() => {
    void reload();
  }, [reload, refreshKey]);
  const apply = useCallback(
    async (direction: "undo" | "redo") => {
      if (busy || !available[direction]) return;
      setBusy(true);
      try {
        await api.post(`${base}/actions/${direction}`);
        onChanged();
        await reload();
      } catch (error: any) {
        onError(error?.response?.data?.detail || `Unable to ${direction}.`);
      } finally {
        setBusy(false);
      }
    },
    [available, base, busy, onChanged, onError, reload],
  );
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (
        target.closest(
          "input, textarea, select, [contenteditable=true], [role=dialog], [role=menu]",
        ) ||
        (!event.ctrlKey && !event.metaKey) ||
        event.altKey
      )
        return;
      const direction =
        event.key.toLowerCase() === "z"
          ? event.shiftKey
            ? "redo"
            : "undo"
          : event.key.toLowerCase() === "y"
            ? "redo"
            : null;
      if (direction && available[direction]) {
        event.preventDefault();
        void apply(direction);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [apply, available]);
  return (
    <div className="flex gap-1" aria-label="Task edit history">
      <button
        className="ws-button ws-outline"
        title="Undo your last task edit (Ctrl/Cmd+Z)"
        aria-label="Undo task edit"
        disabled={busy || !available.undo}
        onClick={() => void apply("undo")}
      >
        <Undo2 size={16} />
        Undo
      </button>
      <button
        className="ws-button ws-outline"
        title="Redo task edit (Ctrl/Cmd+Shift+Z)"
        aria-label="Redo task edit"
        disabled={busy || !available.redo}
        onClick={() => void apply("redo")}
      >
        <Redo2 size={16} />
        Redo
      </button>
    </div>
  );
}
