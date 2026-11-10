import type { QueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { accessQueryOptions } from "./access-query";

/** Default-branch discovery can change the scope while permissions are loading. */
export async function refreshCurrentAccess(client: QueryClient) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const current = useAuthStore.getState();
    if (!current.isAuthenticated || !current.user) return;
    const options = accessQueryOptions();
    const data = await client.fetchQuery(options);
    // Never apply another user/company/branch's response. Immediately load the
    // new scope instead of leaving the reload blocked until the periodic refresh.
    if (JSON.stringify(options.queryKey) !== JSON.stringify(accessQueryOptions().queryKey)) continue;
    const state = useAuthStore.getState();
    if (current.accessToken !== state.accessToken) continue;
    if (state.isAuthenticated && state.user && typeof data.managed === "boolean") {
      state.setUser({ ...state.user, access: data });
    }
    return;
  }
}
