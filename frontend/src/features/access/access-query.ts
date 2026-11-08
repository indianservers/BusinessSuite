import { queryOptions } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore, type AuthUser } from "@/store/authStore";
/** Deduplicate concurrent permission reads only. No permission freshness TTL. */
export function accessQueryOptions() {
  const user = useAuthStore.getState().user;
  return queryOptions({
    queryKey: [
      "suite-access",
      user?.id,
      sessionStorage.getItem("suite-tenant"),
      sessionStorage.getItem("suite-organization"),
      sessionStorage.getItem("suite-branch"),
    ],
    queryFn: ({ signal }) =>
      api
        .get<NonNullable<AuthUser["access"]>>("/access/me", {
          signal,
          progress: false,
        })
        .then((r) => r.data),
    staleTime: 0,
    gcTime: 60000,
    retry: 1,
  });
}
