import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { useAuthStore } from "@/store/authStore";

export default function CompanySwitcher() {
  const { user, setUser } = useAuthStore();
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  if (!user?.access) return null;
  const access = user.access;
  const organizations =
    access.organizations ||
    access.memberships.map((id) => ({
      id,
      name:
        id === access.companyId
          ? access.companyName || "Current workspace"
          : `Workspace ${id}`,
    }));
  return (
    <label className="suite-company">
      <Building2 size={17} />
      <span className="sr-only">Current company</span>
      <select
        aria-label="Current company"
        disabled={busy || organizations.length < 2}
        value={access.companyId}
        onChange={async (event) => {
          const companyId = Number(event.target.value);
          if (
            !organizations.some((org) => org.id === companyId) ||
            companyId === access.companyId
          )
            return;
          setBusy(true);
          await qc.cancelQueries();
          sessionStorage.setItem("suite-organization", String(companyId));
          setUser({ ...user, access: undefined });
          qc.clear();
          window.location.assign("/dashboard");
        }}
      >
        {organizations.map((org) => (
          <option key={org.id} value={org.id}>
            {org.name}
            {org.id === access.companyId ? " (active)" : ""}
          </option>
        ))}
      </select>
      {busy && <span role="status">Switching…</span>}
    </label>
  );
}
