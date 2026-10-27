import type { Activity } from "../registry";
import { Empty } from "./EmptyState";
export function ActivityList({ activities }: { activities: Activity[] }) {
  return activities.length ? (
    <ul className="pa-activity">
      {activities.map((item) => (
        <li key={item.id}>
          <span className="pa-activity-dot" />
          <div>
            <strong>{item.resource_name}</strong>
            <p>{item.action.replace(/_/g, " ")}</p>
          </div>
          <time dateTime={item.created_at}>
            {new Date(item.created_at).toLocaleString()}
          </time>
        </li>
      ))}
    </ul>
  ) : (
    <Empty title="A clean slate">
      Genuine changes in this environment will appear here.
    </Empty>
  );
}
