import { useOperations } from "../../lib/async-progress";
export { beginProgress } from "../../lib/async-progress";
import "./async-progress.css";

/** Background activity must never cover actions or announce routine success. */
export default function AsyncProgress() {
  const { active } = useOperations();
  if (!active.length) return null;
  return <div className="async-progress working" role="progressbar" aria-label="Loading data" aria-valuetext="Loading" aria-busy="true"><div className="async-progress-line"><i /></div></div>;
}
