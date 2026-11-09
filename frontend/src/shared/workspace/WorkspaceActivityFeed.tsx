import { useState } from "react";
import { Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { WorkspaceActivity } from "./workspace-management-types";
export function WorkspaceActivityFeed({ items, loading, error, onRetry }: { items: WorkspaceActivity[]; loading?: boolean; error?: boolean; onRetry: () => void }) {
  const [expanded, setExpanded] = useState(false);
  return <section className="wd-activity" aria-label="Recent workspace activity"><h2><Activity size={19} />Recent activity</h2>{loading && !items.length && <p role="status">Loading workspace activity…</p>}{error && <div role="alert">Activity could not load.<Button variant="ghost" size="sm" onClick={onRetry}>Retry activity</Button></div>}{!loading && !error && !items.length && <p>Workspace changes will appear here as your team works.</p>}<ol>{items.slice(0, expanded ? items.length : 5).map(item => <li key={item.id}><span className="wd-activity-dot" /><div><strong>{item.summary}</strong>{item.actor && <small>{item.actor}</small>}</div>{item.created_at && <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</time>}</li>)}</ol>{items.length > 5 && <Button variant="ghost" size="sm" onClick={() => setExpanded(value => !value)}>{expanded ? "Show less activity" : "View all recent activity"}</Button>}</section>;
}
