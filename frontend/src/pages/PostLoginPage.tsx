import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore, type AuthUser } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { loginDestination } from "@/lib/login";

export default function PostLoginPage() {
  const [params] = useSearchParams();
  const { user, isAuthenticated, isHydrated, setUser } = useAuthStore();
  const [ready, setReady] = useState(false);
  const access = useQuery({
    queryKey: ["dashboard-access", user?.id],
    queryFn: () =>
      api
        .get<NonNullable<AuthUser["access"]>>("/access/me", { progress: false })
        .then((r) => r.data),
    enabled: isHydrated && isAuthenticated && !!user,
    retry: 1,
  });
  useEffect(() => {
    const current = useAuthStore.getState().user;
    if (access.data && current) {
      setUser({ ...current, access: access.data });
      setReady(true);
    }
  }, [access.data, setUser]);
  const destination = loginDestination(params.get("next"));
  if (isHydrated && !isAuthenticated)
    return (
      <Navigate to={`/login?next=${encodeURIComponent(destination)}`} replace />
    );
  if (access.isError)
    return (
      <main className="suite-page">
        <h1>We couldn't load your workspace</h1>
        <p role="alert">Please check your connection and try again.</p>
        <button className="suite-primary" onClick={() => void access.refetch()}>
          Try again
        </button>
      </main>
    );
  if (!ready)
    return (
      <main className="suite-page" role="status">
        Preparing your authorized workspace…
      </main>
    );
  const allowed = canAccessRoute(
    destination.split(/[?#]/)[0],
    user?.role,
    user?.is_superuser,
  );
  return (
    <Navigate
      to={allowed ? destination : "/dashboard"}
      state={
        allowed
          ? undefined
          : {
              notice:
                "That page isn't available for your account. Choose one of your authorized applications.",
            }
      }
      replace
    />
  );
}
