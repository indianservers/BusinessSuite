import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { modules } from "@/lib/moduleCatalog";
import { useLocation, useNavigate } from "react-router-dom";
import { Layers3 } from "lucide-react";
import CompanySwitcher from "@/components/suite/CompanySwitcher";
export default function ModuleSwitcher() {
  const user = useAuthStore((s) => s.user);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const allowed = modules.filter((module) =>
    canAccessRoute(module.homePath, user?.role, user?.is_superuser),
  );
  return (
    <>
      <label className="kf-module-switch">
        <Layers3 size={16} />
        <select
          aria-label="Switch business module"
          value={
            allowed.find(
              (module) =>
                pathname === module.homePath ||
                pathname.startsWith(module.homePath + "/"),
            )?.homePath || "/dashboard"
          }
          onChange={(e) => navigate(e.target.value)}
        >
          <option value="/dashboard">All applications</option>
          {allowed.map((module) => (
            <option key={module.key} value={module.homePath}>
              {module.name}
            </option>
          ))}
        </select>
      </label>
      <CompanySwitcher />
    </>
  );
}
