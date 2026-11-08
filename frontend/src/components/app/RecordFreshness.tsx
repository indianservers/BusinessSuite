import { useSyncExternalStore } from "react";
import { recordCache } from "@/lib/smart-cache/integration";
const idle = { views: 0, pending: 0, health: "idle" };
const subscribe = (listener: () => void) =>
  recordCache?.subscribe(listener) || (() => {});
const snapshot = () => recordCache?.getSyncStatus() || idle;
/** Freshness feedback never hides cached rows or represents them as confirmed writes. */
export default function RecordFreshness() {
  const state = useSyncExternalStore(subscribe, snapshot, snapshot);
  const unavailable =
    state.views > 0 && (state.health === "offline" || state.health === "error");
  return (
    <div
      className="flex min-h-4 items-center justify-end gap-2 text-[10px] text-muted-foreground"
      aria-live={unavailable ? "polite" : "off"}
    >
      {unavailable ? (
        <>
          <span>
            Updates unavailable. Previously loaded information may be out of
            date.
          </span>
          <button
            className="underline"
            onClick={() => void recordCache?.syncModuleChanges(undefined, true)}
          >
            Check again
          </button>
        </>
      ) : state.views > 0 && state.pending > 0 ? (
        <span>Checking for updates…</span>
      ) : null}
    </div>
  );
}
