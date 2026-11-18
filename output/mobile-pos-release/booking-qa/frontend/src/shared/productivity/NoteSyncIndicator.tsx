import type { NoteSyncState } from "./note-sync";

export default function NoteSyncIndicator({ state }: { state?: NoteSyncState }) {
  if (!state || state === "saved") return null;
  return state === "saving"
    ? <span className="notes-sync-ring" role="progressbar" aria-label="Syncing note to server" title="Syncing to server" />
    : <span className="notes-sync-error" role="img" aria-label="Note not synced — draft kept" title="Not synced. Your draft is kept; use Retry save.">!</span>;
}
