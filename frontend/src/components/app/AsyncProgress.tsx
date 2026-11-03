import { useOperations } from "../../lib/async-progress";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
export { beginProgress } from "../../lib/async-progress";
import "./async-progress.css";

/** Background activity must never cover actions or announce routine success. */
export default function AsyncProgress() {
  const { active } = useOperations();
  const fetching = useIsFetching({ predicate: query => query.meta?.progress !== false });
  const mutating = useIsMutating({ predicate: mutation => mutation.meta?.progress !== false });
  if (!active.length && !fetching && !mutating) return null;
  return <div className="async-progress working" role="progressbar" aria-label="Loading data" aria-valuetext="Loading" aria-busy="true"><div className="async-progress-line"><i /></div></div>;
}
