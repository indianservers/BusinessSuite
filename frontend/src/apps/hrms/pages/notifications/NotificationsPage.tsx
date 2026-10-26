import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useState } from "react";
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      toast({ title: "Notifications marked as read" });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Notifications</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Inbox and delivery hooks</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Track in-app alerts now, with email/SMS delivery log hooks ready for providers.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => notifications.refetch()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => markAllRead.mutate()} disabled={markAllRead.isPending}>
            <CheckCheck className="h-4 w-4" />
            Mark all read
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">My notifications</CardTitle>
          <Button
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
          {notifications.isLoading ? (
            <div className="h-28 rounded-lg border bg-muted/30" />
          ) : notifications.data?.items?.length ? (
            notifications.data.items.map((item) => (
              <div key={item.id} className={`rounded-lg border p-4 ${item.is_read ? "bg-card" : "bg-primary/5"}`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Bell className="h-4 w-4 text-primary" />
                      <p className="font-medium">{item.title}</p>
                      {!item.is_read && <Badge>New</Badge>}
                      {item.module && <Badge variant="outline">{item.module}</Badge>}
                      {item.priority !== "normal" && <Badge variant="warning">{item.priority}</Badge>}
                    </div>
                    <div className="mt-2 text-sm text-muted-foreground"><RichTextContent legacyFormat="plain" value={item.message}/></div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{formatDate(item.created_at)}</span>
                      {item.delivery_logs?.map((log) => (
                        <span key={log.id}>{log.channel}: {log.status}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {!item.is_read && (
                      <Button variant="outline" size="sm" onClick={() => markRead.mutate(item.id)}>
                        Mark read
                      </Button>
                    )}
                    {item.action_url && (
                      <Link to={hrmsActionUrl(item.action_url)}>
                        <Button size="sm">
                          <ExternalLink className="h-4 w-4" />
                          Open
                        </Button>
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <p className="rounded-lg border p-6 text-center text-sm text-muted-foreground">No notifications yet.</p>
          )}

          {notifications.data && notifications.data.pages > 1 && (
            <div className="flex items-center justify-between border-t pt-3 text-sm">
              <span className="text-muted-foreground">Page {page} of {notifications.data.pages}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === notifications.data.pages}
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
