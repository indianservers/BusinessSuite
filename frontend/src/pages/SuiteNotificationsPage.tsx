import { useState } from "react";
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
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(params.get("unread") === "1");
  const [mutationError, setMutationError] = useState("");
  const app = params.get("app") || "";
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
      void qc.invalidateQueries({ queryKey: ["suite-notifications"] });
      void qc.invalidateQueries({ queryKey: ["notifications"] });
      void qc.invalidateQueries({ queryKey: ["notifications-unread-count"] });
    },
    onError: () =>
      setMutationError("Could not update notifications. Please try again."),
  });
  const items = (feed.data?.items || [])
    .filter(canSeeNotification)
    .filter((item) => !app || notificationModule(item) === app);
  return (
    <SuitePageShell>
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
          <select
            aria-label="Filter notifications by application"
            value={app}
            onChange={(e) => {
              setPage(1);
              setParams(e.target.value ? { app: e.target.value } : {});
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
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => {
              setPage(1);
              setUnreadOnly(e.target.checked);
            }}
          />
          Unread only
        </label>
        <button className="suite-secondary" onClick={() => void feed.refetch()}>
          Refresh
        </button>
      </div>
      {mutationError && (
        <p className="suite-error" role="alert">
          {mutationError}
        </p>
      )}
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
                      <Link
                        className="suite-primary"
                        to={destination}
                        onClick={() => {
                          if (!item.is_read) markRead.mutate(item.id);
                        }}
                      >
                        Open update
                      </Link>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
          {!items.length && (
            <p className="suite-panel" role="status">
              {unreadOnly
                ? "You're all caught up on this page."
                : "No notifications to show on this page."}
            </p>
          )}
          <nav className="suite-pagination" aria-label="Notification pages">
            <button
              className="suite-secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              className="suite-secondary"
              disabled={page >= (feed.data?.pages || 1)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </nav>
        </>
      )}
    </SuitePageShell>
  );
}
