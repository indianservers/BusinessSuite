import "./notifications-mobile.css";
import { Button } from "@/components/ui/button";
import { refreshNotifications } from "@/lib/notification-cache";
import { NativeSelect } from "@/components/ui/native-select";
import { useLayoutEffect, useState } from "react";
import { useMobile } from "@/components/mobile/useMobile";
import { useNotificationSnooze } from "@/hooks/use-notification-snooze";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { modules } from "@/lib/moduleCatalog";
import { canAccessRoute } from "@/lib/roles";
import SuitePageShell from "@/components/suite/SuitePageShell";
import {
  canSeeNotification,
  notificationDestination,
  notificationModule,
  useNotificationSummary,
  type SuiteNotification,
} from "@/components/suite/notifications";

export default function SuiteNotificationsPage() {
  const user = useAuthStore((s) => s.user);
  const [params, setParams] = useSearchParams();
  const phone = useMobile(480);
  const [localPage, setPage] = useState(1);
  const [localUnreadOnly, setUnreadOnly] = useState(params.get("unread") === "1");
  const [mutationError, setMutationError] = useState("");
  const [localShowSnoozed, setShowSnoozed] = useState(false), [lastSnoozed, setLastSnoozed] = useState<number>();
  const snoozing = useNotificationSnooze();
  const app = params.get("app") || "";
  const requestedPage = Number(params.get("page"));
  const page = phone ? (/^\d+$/.test(params.get("page") || "") && Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1) : localPage;
  const unreadOnly = phone ? params.get("unread") === "1" : localUnreadOnly;
  const showSnoozed = phone ? params.get("snoozed") === "1" : localShowSnoozed;
  // Keep the native checkbox immediate while router transitions settle; history
  // remains authoritative for the feed and synchronizes before the next paint.
  useLayoutEffect(() => { if (phone) setUnreadOnly(unreadOnly); }, [phone, unreadOnly]);
  function updatePhoneView(changes: Record<string, string | null>) {
    setParams(previous => {
      const next = new URLSearchParams(previous);
      for (const [key, value] of Object.entries(changes)) {
        if (value === null) next.delete(key); else next.set(key, value);
      }
      return next;
    });
  }
  const qc = useQueryClient();
  const summary = useNotificationSummary();
  const feed = useQuery({
    queryKey: [
      "suite-notifications",
      user?.id,
      user?.access?.companyId,
      "feed",
      page,
      unreadOnly,
      app,
    ],
    queryFn: () =>
      notificationsApi
        .list({
          page,
          per_page: 20,
          unread_only: unreadOnly,
          app: app || undefined,
        })
        .then((r) => r.data as { items: SuiteNotification[]; pages: number }),
    enabled: !!user?.access,
  });
  const markRead = useMutation({
    mutationFn: (id: number | null) =>
      id === null
        ? notificationsApi.markAllRead()
        : notificationsApi.markRead(id),
    onSuccess: () => {
      setMutationError("");
      return refreshNotifications(qc);
    },
    onError: () =>
      setMutationError("Could not update notifications. Please try again."),
  });
  const items = (feed.data?.items || [])
    .filter(canSeeNotification)
    .filter((item) => !app || notificationModule(item) === app)
    .filter(item => showSnoozed ? snoozing.isSnoozed(item.id) : !snoozing.isSnoozed(item.id));
  return (
    <SuitePageShell className="suite-notifications-page">
      <div className="suite-page-heading">
        <div>
          <h1>Notifications</h1>
          <p>
            Updates across your authorized applications
            {summary.isSuccess ? ` · ${summary.unread} unread` : ""}
          </p>
        </div>
        <button
          className="suite-secondary"
          disabled={markRead.isPending || !summary.unread}
          onClick={() => markRead.mutate(null)}
        >
          Mark all read
        </button>
      </div>
      <div className="suite-toolbar">
        <label>
          Application{" "}
          <NativeSelect
            aria-label="Filter notifications by application"
            value={app}
            onChange={(e) => {
              setPage(1);
              if (phone) updatePhoneView({ app: e.target.value || null, page: null });
              else setParams(e.target.value ? { app: e.target.value } : {});
            }}
          >
            <option value="">All applications</option>
            {modules
              .filter((m) =>
                canAccessRoute(m.homePath, user?.role, user?.is_superuser),
              )
              .map((m) => (
                <option key={m.key} value={m.key}>
                  {m.name}
                </option>
              ))}
          </NativeSelect>
        </label>
        <label>
          <input
            type="checkbox"
            checked={localUnreadOnly}
            onChange={(e) => {
              setPage(1);
              setUnreadOnly(e.target.checked);
              if (phone) updatePhoneView({ unread: e.target.checked ? "1" : null, page: null });
            }}
          />
          Unread only
        </label>
        <Button type="submit" variant="outline" className="suite-secondary" onClick={() => void feed.refetch()}>
          Refresh
        </Button>
      </div>
      {mutationError && (
        <p className="suite-error" role="alert">
          {mutationError}
        </p>
      )}
      <div className="suite-toolbar"><button type="button" className="suite-secondary" aria-pressed={showSnoozed} onClick={() => { setShowSnoozed(!showSnoozed); if (phone) updatePhoneView({ snoozed: !showSnoozed ? "1" : null }); }}>{showSnoozed ? "Show active updates" : "Snoozed on this device"}</button>{lastSnoozed !== undefined && <span role="status">Snoozed for 1 hour. <button type="button" className="suite-secondary" onClick={() => { snoozing.restore(lastSnoozed); setLastSnoozed(undefined); }}>Undo</button></span>}</div>
      {feed.isPending ? (
        <p role="status">Loading notifications…</p>
      ) : feed.isError ? (
        <div role="alert" className="suite-panel">
          Could not load notifications.{" "}
          <button onClick={() => void feed.refetch()}>Try again</button>
        </div>
      ) : (
        <>
          <div className="suite-notification-list">
            {items.map((item) => {
              const destination = notificationDestination(item);
              return (
                <article
                  key={item.id}
                  className={`suite-panel ${item.is_read ? "" : "suite-unread"}`}
                >
                  <div>
                    <h2>
                      <span>{item.title}</span>
                      {!item.is_read && <span className="suite-pill">New</span>}
                    </h2>
                    <p>{item.message}</p>
                    <small>{new Date(item.created_at).toLocaleString()}</small>
                  </div>
                  <div className="suite-inline-actions">
                    <button type="button" className="suite-secondary" onClick={() => { if (snoozing.isSnoozed(item.id)) snoozing.restore(item.id); else { snoozing.snooze(item.id); setLastSnoozed(item.id); } }}>{snoozing.isSnoozed(item.id) ? "Unsnooze" : "Snooze 1 hour"}</button>
                    {!item.is_read && (
                      <button
                        className="suite-secondary"
                        disabled={markRead.isPending}
                        onClick={() => markRead.mutate(item.id)}
                      >
                        Mark read
                      </button>
                    )}
                    {destination && (
                      <Button asChild variant="outline"><Link
                        className="suite-primary"
                        to={destination}
                        onClick={() => {
                          if (!item.is_read) markRead.mutate(item.id);
                        }}
                      >
                        Open update
                      </Link></Button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
          {!items.length && (
            <p className="suite-panel" role="status">
              {showSnoozed ? "No snoozed notifications on this page." : unreadOnly
                ? "You're all caught up on this page."
                : "No notifications to show on this page."}
            </p>
          )}
          <nav className="suite-pagination" aria-label="Notification pages">
            <button
              className="suite-secondary"
              disabled={page <= 1}
              onClick={() => { if (phone) { setPage(page - 1); updatePhoneView({ page: page === 2 ? null : String(page - 1) }); } else setPage((p) => p - 1); }}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              className="suite-secondary"
              disabled={page >= (feed.data?.pages || 1)}
              onClick={() => { if (phone) { setPage(page + 1); updatePhoneView({ page: String(page + 1) }); } else setPage((p) => p + 1); }}
            >
              Next
            </button>
          </nav>
        </>
      )}
    </SuitePageShell>
  );
}
