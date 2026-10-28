import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import { useNotificationSummary } from "./notifications";

export default function SuiteNotificationBell() {
  const summary = useNotificationSummary();
  return (
    <Link
      className="suite-notification-bell"
      to="/notifications"
      aria-label={`Notifications${summary.unread ? `, ${summary.unread} unread` : ""}`}
      title="Suite notifications"
    >
      <Bell size={22} />
      {summary.unread > 0 && (
        <span aria-hidden="true">
          {summary.unread > 99 ? "99+" : summary.unread}
        </span>
      )}
    </Link>
  );
}
