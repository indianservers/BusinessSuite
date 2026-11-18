import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { modules } from "@/lib/moduleCatalog";
import { canAccessRoute } from "@/lib/roles";
import { safeSuiteDestination } from "@/lib/suiteNavigation";

export type SuiteNotification = {
  id: number;
  title: string;
  message: string;
  module?: string | null;
  action_url?: string | null;
  is_read: boolean;
  created_at: string;
};
type Destination = Pick<SuiteNotification, "module" | "action_url">;
const aliases: Record<string, string> = {
  project_management: "pms",
  inventory: "srm",
  finance: "fam",
  engagement: "hrms",
  employees: "hrms",
  attendance: "hrms",
  leave: "hrms",
  payroll: "hrms",
  recruitment: "hrms",
};
export function notificationModule(item: Destination) {
  const url = safeSuiteDestination(item.action_url);
  const fromPath = modules.find(
    (m) => url === m.homePath || url?.startsWith(m.homePath + "/"),
  );
  return fromPath?.key || aliases[item.module || ""] || item.module;
}
export function notificationDestination(item: Destination) {
  const safe = safeSuiteDestination(item.action_url);
  if (safe) return safe;
  const module = modules.find((m) => m.key === notificationModule(item));
  // Legacy HRMS alerts used relative paths such as /leave.
  if (
    module?.key === "hrms" &&
    item.action_url &&
    /^\/[a-z][a-z0-9/-]*$/i.test(item.action_url)
  )
    return safeSuiteDestination(`/hrms${item.action_url}`);
  return null;
}
export function canSeeNotification(item: Destination) {
  const user = useAuthStore.getState().user;
  if (!user?.access) return false;
  const destination = notificationDestination(item);
  const module = modules.find((m) => m.key === notificationModule(item));
  if (module && !canAccessRoute(module.homePath, user.role, user.is_superuser))
    return false;
  if (item.action_url && !destination) return false;
  return destination
    ? canAccessRoute(destination.split(/[?#]/)[0], user.role, user.is_superuser)
    : !item.module || !!module;
}
export function useNotificationSummary() {
  const user = useAuthStore((s) => s.user);
  const query = useQuery({
    queryKey: [
      "suite-notifications",
      user?.id,
      user?.access?.companyId,
      "summary",
    ],
    queryFn: () =>
      api
        .get<{
          groups: (Destination & { count: number })[];
        }>("/notifications/summary", { progress: false })
        .then((r) => r.data),
    enabled: !!user?.access,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
  });
  const groups = (query.data?.groups || []).filter(canSeeNotification);
  return {
    ...query,
    unread: groups.reduce((sum, g) => sum + g.count, 0),
    byModule: groups.reduce<Record<string, number>>((counts, group) => {
      const key = notificationModule(group);
      if (key) counts[key] = (counts[key] || 0) + group.count;
      return counts;
    }, {}),
  };
}
