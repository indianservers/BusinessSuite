import { useMobile } from "@/components/mobile/useMobile";
import "./notifications-mobile.css";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { refreshNotifications } from "@/lib/notification-cache";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, ExternalLink, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { notificationsApi } from "@/services/api";
import { formatDate } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

type Notification = {
  id: number;
  title: string;
  message: string;
  module?: string | null;
  event_type?: string | null;
  action_url?: string | null;
  priority: string;
  is_read: boolean;
  created_at: string;
  delivery_logs?: Array<{ id: number; channel: string; status: string }>;
};

function hrmsActionUrl(url: string) {
  if (url.startsWith("/hrms")) return url;
  if (url.startsWith("/crm") || url.startsWith("/pms")) return url;
  return url.startsWith("/") ? `/hrms${url}` : `/hrms/${url}`;
}

export default function NotificationsPage() {
  usePageTitle("Notifications");
  const qc = useQueryClient();
  const phone = useMobile(480);
  const [actionError, setActionError] = useState("");
  const pendingReadIds = useRef(new Set<number>());
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);

  const notifications = useQuery({
    queryKey: ["notifications", unreadOnly, page],
    queryFn: () =>
      notificationsApi
        .list({ unread_only: unreadOnly, page, per_page: 20 })
        .then((r) => r.data as { items: Notification[]; total: number; pages: number }),
  });

  const markRead = useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSettled: (_data, _error, id) => { pendingReadIds.current.delete(id); },
    onMutate: () => { if (phone) setActionError(""); },
    onError: () => { if (phone) setActionError("Could not mark the notification as read. Try Mark read again."); },
    onSuccess: () => {
      return refreshNotifications(qc);
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onMutate: () => { if (phone) setActionError(""); },
    onError: () => { if (phone) setActionError("Could not mark all notifications as read. Try Mark all read again."); },
    onSuccess: () => {
      toast({ title: "Notifications marked as read" });
      return refreshNotifications(qc);
    },
  });

  const marking = markRead.isPending || markAllRead.isPending;
  const readNotification = (id: number) => {
    if (phone && pendingReadIds.current.has(id)) return;
    if (phone) pendingReadIds.current.add(id);
    markRead.mutate(id);
  };

  return (
    <div className="hrms-notifications space-y-5">
      <div className="hrms-notification-header flex flex-col gap-3 rounded-lg border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Notifications</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Inbox and delivery hooks</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Track in-app alerts now, with email/SMS delivery log hooks ready for providers.
          </p>
        </div>
        <div className="flex gap-2">
          <Button disabled={phone && notifications.isFetching} variant="outline" onClick={() => notifications.refetch()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => { if (!phone || !marking) markAllRead.mutate(); }} disabled={markAllRead.isPending || phone && marking}>
            <CheckCheck className="h-4 w-4" />
            Mark all read
          </Button>
        </div>
      </div>

      {phone && actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      <Card className="hrms-notification-list">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">My notifications</CardTitle>
          <Button
            aria-pressed={unreadOnly}
            variant={unreadOnly ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setUnreadOnly((value) => !value);
              setPage(1);
            }}
          >
            Unread only
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {phone && notifications.isError && <p role="alert">Notifications could not load. <Button disabled={notifications.isFetching} variant="outline" onClick={() => void notifications.refetch()}>Retry notifications</Button></p>}
          {phone && notifications.isError && !notifications.data ? null : notifications.isLoading ? (
            <div role={phone ? "status" : undefined} aria-label={phone ? "Loading notifications" : undefined} className="h-28 rounded-lg border bg-muted/30" />
          ) : notifications.data?.items?.length ? (
            <GroupedRecords scope="apps/hrms/pages/notifications/NotificationsPage:records-1" items={(notifications.data.items) || []} fields={standardRecordGroups((notifications.data.items) || [])} gridClassName="space-y-3" renderItem={(item) => (
              <div data-priority-row data-priority={item.priority} key={item.id} className={`hrms-notification-record rounded-lg border p-4 ${item.is_read ? "bg-card" : "bg-primary/5"}`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Bell className="h-4 w-4 text-primary" />
                      <p className="font-medium">{item.title}</p>
                      {!item.is_read && <Badge>New</Badge>}
                      {item.module && <Badge variant="outline">{item.module}</Badge>}
                      {item.priority !== "normal" && <Badge data-priority-badge data-priority={item.priority} variant="warning">{item.priority}</Badge>}
                    </div>
                    <div className="mt-2 text-sm text-muted-foreground"><RichTextContent legacyFormat="plain" value={item.message}/></div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{formatDate(item.created_at)}</span>
                      {phone && !!item.delivery_logs?.length ? <details className="hrms-notification-delivery"><summary>Delivery details ({item.delivery_logs.length})</summary><div>{item.delivery_logs.map(log => <span key={log.id}>{log.channel}: {log.status}</span>)}</div></details> : item.delivery_logs?.map((log) => (
                        <span key={log.id}>{log.channel}: {log.status}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {!item.is_read && (
                      <Button variant="outline" size="sm" disabled={phone && marking} onClick={() => readNotification(item.id)}>
                        Mark read
                      </Button>
                    )}
                    {item.action_url && (phone ? (
                      <Button asChild size="sm"><Link to={hrmsActionUrl(item.action_url)} onClick={() => { if (!item.is_read) readNotification(item.id); }}><ExternalLink className="h-4 w-4" />Open</Link></Button>
                    ) : (
                      <Link to={hrmsActionUrl(item.action_url)} onClick={() => { if (!item.is_read) readNotification(item.id); }}>
                        <Button size="sm">
                          <ExternalLink className="h-4 w-4" />
                          Open
                        </Button>
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            )}/>
          ) : (
            <p className="rounded-lg border p-6 text-center text-sm text-muted-foreground">No notifications yet.</p>
          )}

          {notifications.data && notifications.data.pages > 1 && (
            <div className="flex items-center justify-between border-t pt-3 text-sm">
              <span className="text-muted-foreground">Page {page} of {notifications.data.pages}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 1 || phone && notifications.isFetching} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === notifications.data.pages || phone && notifications.isFetching}
                  onClick={() => setPage((p) => Math.min(notifications.data?.pages || p, p + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
