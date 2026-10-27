import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { useRealtimeStore } from "@/apps/project-management/realtime";
export default function MessagingNavLink({
  workspaceId,
  className = "ws-rail-item",
  collapsed = false,
}: {
  workspaceId?: number;
  className?: string;
  collapsed?: boolean;
}) {
  const { user } = useAuthStore();
  const location=useLocation();
  const module=location.pathname.split("/")[1];
  const route=`/${["pms","crm","hrms","srm","fam"].includes(module)?module:"pms"}/messages`;
  const connected=useRealtimeStore(s=>s.connected&&s.transport==="websocket");
  const event = useRealtimeStore((s) => s.events[0]);
  const query = useQuery({
    queryKey: ["chat-unread", user?.id],
    enabled: !!user,
    queryFn: async () =>
      (
        await api.get<{ unread: number }>(
          "/collaboration/unread", {progress:false},
        )
      ).data,
    refetchInterval: connected ? false : 30000,
  });
  useEffect(() => {
    if (event?.type === "chat.invalidate") void query.refetch();
  }, [event]);
  return (
    <Link
      to={`${route}${workspaceId ? `?workspace=${workspaceId}` : ""}`}
      className={className}
      aria-current={location.pathname===route?"page":undefined}
      aria-label={`Messages${query.data?.unread ? `, ${query.data.unread} unread` : ""}`}
      title="Messages"
    >
      <MessageSquare size={20} />
      {!collapsed && <span>Messages</span>}
      {!!query.data?.unread && (
        <b
          style={{
            fontSize: 10,
            padding: "1px 5px",
            borderRadius: 10,
            background: "hsl(var(--primary))",
            color: "white",
          }}
        >
          {query.data.unread > 99 ? "99+" : query.data.unread}
        </b>
      )}
    </Link>
  );
}
