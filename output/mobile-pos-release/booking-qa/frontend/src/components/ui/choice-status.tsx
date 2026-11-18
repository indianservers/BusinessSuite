import { Loader2 } from "lucide-react";

/** Normal flow only: never floats over dropdown actions, adjacent fields or buttons. */
export function ChoiceStatus({ loading, empty, error, loadingText = "Loading choices…", emptyText = "No data found" }: {
  loading: boolean; empty: boolean; error?: boolean; loadingText?: string; emptyText?: string;
}) {
  if (!loading && (error || !empty)) return null;
  return <span role="status" aria-live="polite" className="flex min-w-0 items-center gap-1.5 py-1 text-xs text-muted-foreground">
    {loading && <Loader2 aria-hidden="true" className="h-3 w-3 shrink-0 motion-safe:animate-spin" />}
    <span>{loading ? loadingText : emptyText}</span>
  </span>;
}
