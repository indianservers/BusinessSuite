import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { products } from "@/lib/products";
import { useLocation, useNavigate } from "react-router-dom";
import { Layers3 } from "lucide-react";
export default function ModuleSwitcher() {
  const user = useAuthStore((s) => s.user);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const allowed = Object.values(products).filter((p) =>
    canAccessRoute(p.homePath, user?.role, user?.is_superuser),
  );
  return (
    <>
    <label className="kf-module-switch">
      <Layers3 size={16} />
      <select
        aria-label="Switch business module"
        value={
          allowed.find(
            (p) =>
              pathname === p.homePath || pathname.startsWith(p.homePath + "/"),
          )?.homePath || ""
        }
        onChange={(e) => navigate(e.target.value)}
      >
        <option value="" disabled>
          Business Suite
        </option>
        {allowed.map((p) => (
          <option key={p.key} value={p.homePath}>
            {p.shortName}
          </option>
        ))}
        <option value="/">All applications</option>
      </select>
    </label>
    {!!user?.access && user.access.memberships.length > 1 && <label className="kf-module-switch"><span>Company</span><select aria-label="Current organization context" value={user.access.companyId} onChange={e => { sessionStorage.setItem("suite-organization", e.target.value); window.location.reload(); }}>{user.access.memberships.map(id => <option value={id} key={id}>Company {id}</option>)}</select></label>}
    </>
  );
}
