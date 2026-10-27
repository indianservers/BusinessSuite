import { useSyncExternalStore } from "react";

type Operation = { id: number; label: string; started: number };
type State = { active: Operation[]; result: "success" | "error" | null; error?: string };
let state: State = { active: [], result: null };
const listeners = new Set<() => void>();
export function useOperations() {
  return useSyncExternalStore(listener => { listeners.add(listener); return () => { listeners.delete(listener); }; }, () => state);
}
function update(change: Partial<State> | ((current: State) => Partial<State>)) {
  state = { ...state, ...(typeof change === "function" ? change(state) : change) };
  listeners.forEach(listener => listener());
}
let sequence = 0;
let clearTimer: ReturnType<typeof setTimeout>;

/** Track concurrent page loads and actions until every operation settles. */
export function beginProgress(label: string) {
  const id = ++sequence;
  clearTimeout(clearTimer);
  update(s => ({ active: [...s.active, { id, label, started: Date.now() }], result: s.active.length ? s.result : null, error: s.active.length ? s.error : undefined }));
  let finished = false;
  return (success = true, error?: string) => {
    if (finished) return;
    finished = true;
    update(s => ({ active: s.active.filter(op => op.id !== id), result: success ? s.result === "error" ? "error" : "success" : "error", error: success ? s.error : error }));
    clearTimeout(clearTimer);
    if (!state.active.length) clearTimer = setTimeout(() => update({ result: null }), state.result === "error" ? 8000 : 1200);
  };
}
