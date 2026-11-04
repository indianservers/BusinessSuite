import { refreshNotifications } from "@/lib/notification-cache";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Bell, X, ArrowLeft } from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { canSeeNotification, notificationDestination, useNotificationSummary, type SuiteNotification } from "./notifications";

export default function SuiteNotificationBell() {
  const summary = useNotificationSummary();
  const user = useAuthStore(s => s.user);
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<SuiteNotification | null>(null);
  const [page, setPage] = useState(1);
  const feed = useQuery({
    queryKey: ["suite-notifications", user?.id, user?.access?.companyId, "bell", page],
    queryFn: () => notificationsApi.list({ page, per_page: 20 }).then(r => r.data as { items: SuiteNotification[]; pages: number }),
    enabled: open && !!user?.access,
    staleTime: 30_000,
  });
  const markRead = useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => {
      return refreshNotifications(qc);
    },
  });
  const items = (feed.data?.items || []).filter(canSeeNotification);
  const destination = selected ? notificationDestination(selected) : null;
  return (
    <Popover.Root open={open} onOpenChange={value => { setOpen(value); if (!value) { setSelected(null); setPage(1); markRead.reset(); } }}>
      <Popover.Trigger asChild>
        <button type="button" className="suite-notification-bell border-0 bg-transparent" aria-label={`Notifications${summary.unread ? `, ${summary.unread} unread` : ""}`} title="Suite notifications">
          <Bell size={22} />
          {summary.unread > 0 && <span aria-hidden="true">{summary.unread > 99 ? "99+" : summary.unread}</span>}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" side="bottom" sideOffset={8} collisionPadding={12} aria-label="Notifications" className="z-50 flex w-[min(24rem,calc(100vw-1.5rem))] max-h-[min(36rem,var(--radix-popover-content-available-height))] flex-col rounded-xl border bg-popover text-popover-foreground shadow-xl">
          <div className="flex items-center justify-between border-b p-4">
            <h2 className="font-semibold">Notifications</h2>
            <Popover.Close aria-label="Close notifications" className="rounded p-1 hover:bg-muted"><X size={18} /></Popover.Close>
          </div>
          <div className="overflow-y-auto overscroll-contain">
            {selected ? <div className="space-y-3 p-4">
              <button className="flex items-center gap-2 text-sm text-muted-foreground" onClick={() => setSelected(null)}><ArrowLeft size={16} />Back to notifications</button>
              <h3 className="font-semibold break-words">{selected.title}</h3>
              <p className="whitespace-pre-wrap break-words text-sm">{selected.message}</p>
              <p className="text-xs text-muted-foreground">{new Date(selected.created_at).toLocaleString()}</p>
              {markRead.isError && <p role="alert" className="text-sm text-destructive">Could not mark this notification as read. <button onClick={() => markRead.mutate(selected.id)}>Try again</button></p>}
              {destination && <Link className="inline-flex rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground" to={destination} onClick={() => setOpen(false)}>Open related update</Link>}
            </div> : feed.isPending ? <p role="status" className="p-4 text-sm">Loading notifications…</p> : feed.isError ? <div role="alert" className="p-4 text-sm">Could not load notifications. <button onClick={() => void feed.refetch()}>Try again</button></div> : <>
              {!items.length && <p role="status" className="p-4 text-sm text-muted-foreground">No notifications to show on this page.</p>}
              {items.map(item => <button key={item.id} className={`block w-full space-y-1 border-b p-4 text-left hover:bg-muted focus-visible:bg-muted ${item.is_read ? "" : "bg-primary/5"}`} onClick={() => { setSelected(item); markRead.reset(); if (!item.is_read) markRead.mutate(item.id); }}>
                <div className="flex items-start gap-2"><span className="font-medium text-sm break-words">{item.title}</span>{!item.is_read && <span className="ml-auto shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">New</span>}</div>
                <p className="line-clamp-2 break-words text-sm text-muted-foreground">{item.message}</p>
                <p className="text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
              </button>)}
              {(feed.data?.pages || 1) > 1 && <nav aria-label="Notification pages" className="flex items-center justify-between p-3 text-sm">
                <button disabled={page <= 1} className="disabled:opacity-40" onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page}</span><button disabled={page >= (feed.data?.pages || 1)} className="disabled:opacity-40" onClick={() => setPage(p => p + 1)}>Next</button>
              </nav>}
            </>}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
