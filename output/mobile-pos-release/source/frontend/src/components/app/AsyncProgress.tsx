import { useAuthStore } from "@/store/authStore";
import { useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import {
  Check,
  AlertCircle,
  Loader2,
  Minus,
  X,
  Upload,
  Download,
  FileText,
  Layers,
} from "lucide-react";
import {
  progress,
  getOperations,
  useOperations,
  type ActiveOperation,
} from "@/lib/async-progress";
import { useLoadingContext } from "@/hooks/use-loading-context";
import RouteProgress from "./RouteProgress";
export { beginProgress } from "@/lib/async-progress";
import "./async-progress.css";

export function MicroLoader({
  title,
  className = "",
}: {
  title: string;
  className?: string;
}) {
  return (
    <span
      role="status"
      aria-label={title}
      className={`smart-micro ${className}`}
    >
      <Loader2 aria-hidden="true" />
      <span className="sr-only">{title}</span>
    </span>
  );
}

export function ProgressDetails({
  operation: op,
}: {
  operation: ActiveOperation;
}) {
  const finished = op.status !== "running" && op.status !== "cancelling";
  const Icon =
    op.status === "success"
      ? Check
      : op.status === "error"
        ? AlertCircle
        : op.operationType === "upload"
          ? Upload
          : op.operationType === "download" || op.operationType === "export"
            ? Download
            : op.operationType === "generate"
              ? FileText
              : Layers;
  const title =
    op.status === "success"
      ? op.successTitle || `${op.title} — Complete`
      : op.status === "error"
        ? op.errorTitle || `Unable to finish: ${op.title}`
        : op.title;
  return (
    <div className={`smart-progress-body state-${op.status}`}>
      <span className="smart-progress-icon">
        <Icon aria-hidden="true" />
      </span>
      <Dialog.Title className="smart-progress-title">{title}</Dialog.Title>
      <Dialog.Description
        id="smart-progress-description"
        className="smart-progress-description"
      >
        {op.status === "error"
          ? op.error
          : op.description ||
            (finished
              ? "The operation has finished."
              : "Please wait while this operation completes.")}
      </Dialog.Description>
      {!finished && (
        <div className="smart-progress-measure">
          <span>
            <Loader2 aria-hidden="true" />{" "}
            {op.status === "cancelling"
              ? "Cancelling…"
              : op.steps?.find((s) => s.status === "active")?.label ||
                "In progress"}
          </span>
          {op.progress != null && <strong>{Math.round(op.progress)}%</strong>}
        </div>
      )}
      <div
        className={`smart-progress-track ${op.progress == null && !finished ? "indeterminate" : ""}`}
        role="progressbar"
        aria-label={title}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={op.progress}
        aria-valuetext={
          op.status === "error"
            ? "Failed"
            : op.status === "success"
              ? "Complete"
              : op.progress == null
                ? "In progress"
                : `${Math.round(op.progress)}%`
        }
      >
        <i
          style={op.progress == null ? undefined : { width: `${op.progress}%` }}
        />
      </div>
      {!!op.steps?.length && (
        <ol className="smart-progress-steps" aria-label="Operation stages">
          {op.steps.map((step, index) => (
            <li key={step.id} data-state={step.status}>
              <span>
                {step.status === "completed" ? (
                  <Check aria-hidden="true" />
                ) : step.status === "failed" ? (
                  <AlertCircle aria-hidden="true" />
                ) : step.status === "active" ? (
                  <Loader2 aria-hidden="true" />
                ) : (
                  index + 1
                )}
              </span>
              {step.label}
              <small>{step.status}</small>
            </li>
          ))}
        </ol>
      )}
      <footer className="smart-progress-actions">
        {!finished && op.backgroundable && (
          <button onClick={() => progress.minimize(op.id)}>
            <Minus size={15} />
            Run in background
          </button>
        )}
        {!finished && op.cancellable && (
          <button
            disabled={op.status === "cancelling"}
            onClick={() => void progress.cancel(op.id)}
          >
            Cancel
          </button>
        )}
        {op.status === "error" && op.onRetry && (
          <button
            onClick={() => {
              progress.dismiss(op.id);
              op.onRetry?.();
            }}
          >
            Retry
          </button>
        )}
        {finished && op.onViewDetails && (
          <button onClick={op.onViewDetails}>View details</button>
        )}
        {finished && (
          <button
            className="smart-progress-primary"
            onClick={() => progress.dismiss(op.id)}
          >
            Dismiss
          </button>
        )}
      </footer>
    </div>
  );
}

/** One host arbitrates simultaneous operations. Routine reads never open a dialog. */
export default function AsyncProgress() {
  const state = useOperations();
  const context = useLoadingContext();
  const fetching = useIsFetching({
    predicate: (q) => q.meta?.progress !== false && q.state.data === undefined,
  });
  const mutating = useIsMutating({
    predicate: (m) => m.meta?.progress !== false,
  });
  const modal =
    state.active.find((op) => op.mode === "modal" && !op.minimized) ||
    state.settled.find((op) => op.id === state.expandedId) ||
    state.active.find((op) => op.id === state.expandedId) ||
    state.settled.find((op) => op.mode === "modal" && !op.minimized);
  const dock = [
    ...state.active.filter((op) => op.minimized || op.mode === "background"),
    ...state.settled.filter((op) => op.minimized || op.mode === "background"),
  ];
  const micro = state.active.filter((op) => op.mode === "micro");
  const label = micro[micro.length - 1]?.title || context.title;
  useEffect(() => {
    const identity = () => {
      const user = useAuthStore.getState().user;
      return `${user?.id}:${user?.access?.companyId}`;
    };
    let currentIdentity = identity();
    const clear = () => {
      const snapshot = getOperations();
      for (const op of [...snapshot.active, ...snapshot.settled])
        progress.dismiss(op.id);
    };
    const unsubscribe = useAuthStore.subscribe(() => {
      const next = identity();
      if (next !== currentIdentity) {
        currentIdentity = next;
        clear();
      }
    });
    window.addEventListener("suite:organization-changed", clear);
    return () => {
      unsubscribe();
      window.removeEventListener("suite:organization-changed", clear);
    };
  }, []);
  return (
    <>
      <RouteProgress />
      <span className="sr-only" role="status" aria-live="polite">
        {state.settled[state.settled.length - 1]?.status === "success"
          ? state.settled[state.settled.length - 1]?.successTitle ||
            `${state.settled[state.settled.length - 1]?.title} complete`
          : state.settled[state.settled.length - 1]?.status === "error"
            ? state.settled[state.settled.length - 1]?.error
            : ""}
      </span>
      {!modal && (micro.length > 0 || fetching > 0 || mutating > 0) && (
        <div
          className="async-progress working"
          role="progressbar"
          aria-label={label}
          aria-valuetext={label}
          aria-busy="true"
        >
          <div className="async-progress-line">
            <i />
          </div>
        </div>
      )}
      <Dialog.Root
        open={!!modal}
        onOpenChange={(open) => {
          if (!open && modal) {
            if (modal.status === "success" || modal.status === "error")
              progress.dismiss(modal.id);
            else if (modal.backgroundable) progress.minimize(modal.id);
          }
        }}
      >
        {modal && (
          <Dialog.Portal>
            <Dialog.Overlay className="smart-progress-overlay" />
            <Dialog.Content
              className="smart-progress-dialog"
              aria-describedby="smart-progress-description"
              onPointerDownOutside={(e) => e.preventDefault()}
              onEscapeKeyDown={(e) => {
                if (modal.status === "running" && !modal.backgroundable)
                  e.preventDefault();
              }}
            >
              <ProgressDetails operation={modal} />
              {modal.backgroundable && modal.status === "running" && (
                <button
                  className="smart-progress-minimize"
                  aria-label="Minimize progress"
                  onClick={() => progress.minimize(modal.id)}
                >
                  <Minus size={18} />
                </button>
              )}
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </Dialog.Root>
      {!!dock.length && (
        <aside
          className="smart-progress-dock"
          aria-label="Background operations"
        >
          {dock.map((op) => (
            <div key={op.id}>
              <button onClick={() => progress.restore(op.id)}>
                {op.status === "running" ? (
                  <Loader2 aria-hidden="true" />
                ) : op.status === "error" ? (
                  <AlertCircle aria-hidden="true" />
                ) : (
                  <Check aria-hidden="true" />
                )}
                <span>
                  <strong>
                    {op.status === "success"
                      ? op.successTitle || op.title
                      : op.title}
                  </strong>
                  <small>
                    {op.status === "running"
                      ? op.progress == null
                        ? "In progress"
                        : `${Math.round(op.progress)}%`
                      : op.status === "error"
                        ? "Needs attention"
                        : "Complete"}
                  </small>
                </span>
              </button>
              {op.status !== "running" && (
                <button
                  aria-label={`Dismiss ${op.title}`}
                  onClick={() => progress.dismiss(op.id)}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          ))}
        </aside>
      )}
    </>
  );
}
