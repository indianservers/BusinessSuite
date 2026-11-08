import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore, type AuthUser } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { loginDestination } from "@/lib/login";

export default function PostLoginPage() {
  const [params] = useSearchParams();
  const { user, isAuthenticated, isHydrated, setUser } = useAuthStore();
  const qc = useQueryClient();
  const [ready, setReady] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<number | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const [selecting, setSelecting] = useState(false);
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
  async function chooseCompany(companyId: number) {
    setSelecting(true);
    setSelectionError("");
    try {
      // Validate the selected membership before applying it to other requests.
      const { data } = await api.get<NonNullable<AuthUser["access"]>>("/access/me", {
        headers: { "X-Suite-Organization": String(companyId) },
      });
      sessionStorage.setItem("suite-organization", String(companyId));
      sessionStorage.removeItem("suite-branch");
      qc.clear();
      qc.setQueryData(["dashboard-access", user?.id], data);
      const current = useAuthStore.getState().user;
      if (current) setUser({ ...current, access: data });
      setSelectedCompany(companyId);
    } catch {
      setSelectionError("We couldn't open that company. Please try again.");
    } finally {
      setSelecting(false);
    }
  }
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
        Preparing your authorized workspaceâ€¦
      </main>
    );
  const organizations = access.data?.organizations || [];
  if (organizations.length > 1 && selectedCompany === null)
    return (
      <main className="suite-page">
        <h1>Choose your company</h1>
        <p>Your account has access to multiple companies. Choose one to continue.</p>
        {selectionError && <p role="alert">{selectionError}</p>}
        <div className="suite-form">
          {organizations.map((company) => (
            <button key={company.id} className="suite-secondary" disabled={selecting}
              onClick={() => void chooseCompany(company.id)}>
              {company.name}{company.id === access.data?.companyId ? " (Default)" : ""}
            </button>
          ))}
        </div>
        {selecting && <p role="status">Opening company…</p>}
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
