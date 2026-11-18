import { useSyncExternalStore } from "react";

export type ProgressStep = {
  id: string;
  label: string;
  status: "pending" | "active" | "completed" | "failed";
};
export type ProgressOperation = {
  id: string;
  title: string;
  description?: string;
  module?: string;
  operationType?:
    | "navigation"
    | "fetch"
    | "save"
    | "upload"
    | "download"
    | "import"
    | "export"
    | "generate"
    | "sync"
    | "process";
  progress?: number;
  steps?: ProgressStep[];
  mode?: "micro" | "modal" | "background";
  cancellable?: boolean;
  backgroundable?: boolean;
  onCancel?: () => void | Promise<void>;
  onRetry?: () => void;
  onViewDetails?: () => void;
  successTitle?: string;
  errorTitle?: string;
  route?: string;
};
export type ActiveOperation = ProgressOperation & {
  label: string;
  started: number;
  status: "running" | "cancelling" | "success" | "error" | "cancelled";
  error?: string;
  minimized: boolean;
  token: symbol;
};
type State = {
  active: ActiveOperation[];
  settled: ActiveOperation[];
  result: "success" | "error" | null;
  error?: string;
  expandedId?: string;
};
let state: State = { active: [], settled: [], result: null };
const listeners = new Set<() => void>();
export const getOperations = () => state;
export const subscribeOperations = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export function useOperations() {
  return useSyncExternalStore(
    subscribeOperations,
    getOperations,
    getOperations,
  );
}
function emit(next: State) {
  state = next;
  listeners.forEach((listener) => listener());
}
let sequence = 0;
const safeProgress = (value?: number) =>
  value == null || !Number.isFinite(value)
    ? undefined
    : Math.max(0, Math.min(100, value));
function change(
  id: string,
  fn: (op: ActiveOperation) => ActiveOperation,
  token?: symbol,
) {
  emit({
    ...state,
    active: state.active.map((op) =>
      op.id === id && (!token || op.token === token) ? fn(op) : op,
    ),
  });
}
function settle(
  id: string,
  status: ActiveOperation["status"],
  error?: string,
  token?: symbol,
  fromCancellation = false,
) {
  const op = state.active.find(
    (op) => op.id === id && (!token || token === op.token),
  );
  if (
    !op ||
    (op.status === "cancelling" && status !== "cancelled" && !fromCancellation)
  )
    return;
  const finished = {
    ...op,
    status,
    error,
    ...(status === "success" ? { progress: 100 } : {}),
  };
  const keep = op.mode !== "micro" && status !== "cancelled";
  emit({
    ...state,
    active: state.active.filter((item) => item !== op),
    settled: keep ? [...state.settled, finished].slice(-20) : state.settled,
    result:
      status === "error" ? "error" : status === "success" ? "success" : null,
    error,
  });
}
export const progress = {
  start(input: ProgressOperation) {
    if (input.mode === "background" && !input.backgroundable)
      throw new Error(
        "Background progress requires a background-capable operation",
      );
    if (!input.title.trim())
      throw new Error("Progress requires an operation title");
    if (
      state.active.some((op) => op.id === input.id) ||
      state.settled.some((op) => op.id === input.id)
    )
      throw new Error(`Operation already exists: ${input.id}`);
    const token = Symbol(input.id);
    const op: ActiveOperation = {
      ...input,
      title: input.title.trim(),
      label: input.title.trim(),
      progress: safeProgress(input.progress),
      mode: input.mode || "micro",
      cancellable: Boolean(input.cancellable && input.onCancel),
      backgroundable: Boolean(input.backgroundable),
      route:
        input.route ??
        (typeof window !== "undefined" ? window.location.pathname : undefined),
      started: Date.now(),
      status: "running",
      minimized: input.mode === "background",
      token,
    };
    emit({
      ...state,
      active: [...state.active, op],
      result: null,
      error: undefined,
    });
    return {
      id: op.id,
      update: (
        patch: Partial<
          Pick<
            ProgressOperation,
            "title" | "description" | "progress" | "steps"
          >
        >,
      ) =>
        change(
          op.id,
          (current) => ({
            ...current,
            ...patch,
            label: patch.title || current.title,
            progress:
              "progress" in patch
                ? safeProgress(patch.progress)
                : current.progress,
          }),
          token,
        ),
      complete: () => settle(op.id, "success", undefined, token),
      fail: (error: unknown) =>
        settle(
          op.id,
          "error",
          error instanceof Error
            ? error.message
            : String(error || "Please try again."),
          token,
        ),
      dispose: () => progress.dismiss(op.id, token),
    };
  },
  update(
    id: string,
    patch: Partial<
      Pick<ProgressOperation, "title" | "description" | "progress" | "steps">
    >,
  ) {
    change(id, (op) => ({
      ...op,
      ...patch,
      label: patch.title || op.title,
      progress:
        "progress" in patch ? safeProgress(patch.progress) : op.progress,
    }));
  },
  complete: (id: string) => settle(id, "success"),
  fail: (id: string, error: unknown) =>
    settle(id, "error", error instanceof Error ? error.message : String(error)),
  async cancel(id: string) {
    const op = state.active.find((op) => op.id === id);
    if (!op?.cancellable || !op.onCancel || op.status !== "running") return;
    change(id, (item) => ({ ...item, status: "cancelling" }), op.token);
    try {
      await op.onCancel();
      settle(id, "cancelled", undefined, op.token);
    } catch (error) {
      settle(
        id,
        "error",
        error instanceof Error
          ? error.message
          : "Unable to cancel this operation.",
        op.token,
        true,
      );
    }
  },
  minimize(id: string) {
    change(id, (op) => (op.backgroundable ? { ...op, minimized: true } : op));
    if (state.expandedId === id) emit({ ...state, expandedId: undefined });
  },
  restore(id: string) {
    change(id, (op) => ({ ...op, minimized: false }));
    emit({ ...state, expandedId: id });
  },
  dismiss(id: string, token?: symbol) {
    emit({
      ...state,
      active: state.active.filter(
        (op) => op.id !== id || (!!token && op.token !== token),
      ),
      settled: state.settled.filter(
        (op) => op.id !== id || (!!token && op.token !== token),
      ),
      expandedId: state.expandedId === id ? undefined : state.expandedId,
    });
  },
  leaveRoute(route: string) {
    const remove = (op: ActiveOperation) =>
      op.route && op.route !== route && !(op.backgroundable && op.minimized);
    emit({
      ...state,
      active: state.active.filter((op) => !remove(op)),
      settled: state.settled.filter((op) => !remove(op)),
      expandedId: undefined,
    });
  },
};
export const operationId = (prefix = "operation") => `${prefix}-${++sequence}`;
/** Backwards-compatible, non-blocking feedback for existing request callers. */
export function beginProgress(label: string) {
  const operation = progress.start({
    id: operationId("request"),
    title: label,
    mode: "micro",
  });
  return (success = true, error?: string) =>
    success
      ? operation.complete()
      : operation.fail(error || "Unable to complete this operation.");
}
