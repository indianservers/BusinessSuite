import type { QueryClient } from "@tanstack/react-query";

/** Keep all notification views and the shared bell/sidebar badges in sync. */
export async function refreshNotifications(client: QueryClient) {
  await Promise.all([
    "suite-notifications",
    "notifications",
    "profile-notifications",
    "notifications-unread-count",
  ].map(key => client.invalidateQueries({ queryKey: [key] })));
}
