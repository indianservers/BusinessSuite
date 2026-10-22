import { create } from "zustand";

type Operation = { id: number; label: string; started: number };
export const useOperations = create<{ active: Operation[]; result: "success" | "error" | null; error?: string }>(() => ({ active: [], result: null, error: undefined }));
let sequence = 0;
let clearTimer: ReturnType<typeof setTimeout>;

/** Track foreground work explicitly; realtime polling should remain quiet. */
export function beginProgress(label: string) {
  const id = ++sequence;
  clearTimeout(clearTimer);
  useOperations.setState(s => ({ active: [...s.active, { id, label, started: Date.now() }], result: null, error: undefined }));
  let finished = false;
  return (success = true, error?: string) => {
    if (finished) return;
    finished = true;
    useOperations.setState(s => ({ active: s.active.filter(op => op.id !== id), result: success ? s.result === "error" ? "error" : "success" : "error", error: success ? s.error : error }));
    clearTimeout(clearTimer);
    clearTimer = setTimeout(() => useOperations.setState({ result: null }), success ? 2400 : 8000);
  };
}
