import { Link, useLocation } from "react-router-dom";
import {
  Box,
  Layers3,
  Mail,
  ShieldCheck,
  UserCircle,
  Users,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/store/authStore";
import { getRoleLabel, getRoleNav, canAccessRoute } from "@/lib/roles";
import {
  BUSINESS_SUITE_DISPLAY_NAME,
  getProductDisplayName,
  getProductForContext,
} from "@/lib/products";
import { usePageTitle } from "@/hooks/use-page-title";
import { PageHeader } from "@/design-system/components";
import SharedProfilePage from "../features/profiles/ProfilePage";
export default function ModuleProfilePage() { return <><SharedProfilePage /><details className="mx-6 my-4"><summary className="cursor-pointer text-sm text-muted-foreground">Workspace access summary</summary><ModuleAccessSummary /></details></>; }
function ModuleAccessSummary() {
  const { pathname } = useLocation();
  const user = useAuthStore((s) => s.user);
  const product = getProductForContext(
    pathname,
    user?.role,
    user?.is_superuser,
  );
  const role = getRoleLabel(user?.role, user?.is_superuser);
  usePageTitle(`${product.shortName} Profile`);
  const links = getRoleNav(user?.role, user?.is_superuser, pathname)
    .filter(
      (item) =>
        canAccessRoute(item.to, user?.role, user?.is_superuser) &&
        item.to !== pathname,
    )
    .slice(0, 8);
  return (
    <div className="space-y-6">
      <PageHeader
        icon={UserCircle}
        title={`${product.shortName} Profile`}
        description="Your workspace identity and module access summary."
      />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>
              Your personal and workspace details.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="kf-profile-identity">
              <div className="kf-profile-avatar">
                {(user?.name || user?.email || "?").charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <h2 className="text-xl font-semibold">
                  {user?.name || user?.email?.split("@")[0]}
                </h2>
                <p className="break-all text-sm text-muted-foreground mt-1">
                  {user?.email}
                </p>
                <div className="flex gap-2 flex-wrap mt-3">
                  <Badge variant="secondary">{role}</Badge>
                </div>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                {
                  icon: Box,
                  label: "Module",
                  value: product.name,
                  detail: getProductDisplayName(product),
                },
                {
                  icon: Layers3,
                  label: "Suite",
                  value: BUSINESS_SUITE_DISPLAY_NAME,
                  detail: "Connected business workspace",
                },
                {
                  icon: ShieldCheck,
                  label: "Role",
                  value: role,
                  detail: "Access enforced by the server",
                },
                {
                  icon: Users,
                  label: "Workspace",
                  value: product.shortName,
                  detail: "Record access follows membership",
                },
              ].map((item) => (
                <div key={item.label} className="kf-profile-tile">
                  <span className="kf-feature-icon">
                    <item.icon size={22} />
                  </span>
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {item.label}
                    </p>
                    <p className="font-semibold mt-1">{item.value}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {item.detail}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Access Summary</CardTitle>
            <CardDescription>
              Your access level, permissions and module availability.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="kf-profile-tile">
              <span className="kf-feature-icon">
                <Mail size={22} />
              </span>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Email</p>
                <p className="font-semibold break-all">{user?.email}</p>
              </div>
            </div>
            <div className="kf-profile-tile">
              <span className="kf-feature-icon">
                <ShieldCheck size={22} />
              </span>
              <div>
                <h3 className="font-semibold">
                  {user?.is_superuser ? "Super admin access" : "Module access"}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {user?.is_superuser
                    ? "Administrative permissions across enabled modules."
                    : "Actions depend on your role and record permissions."}
                </p>
              </div>
            </div>
            <section>
              <h3 className="font-semibold mb-3">Available pages</h3>
              <div className="kf-profile-links">
                {links.map((item) => (
                  <Link key={item.to} to={item.to}>
                    <item.icon size={17} />
                    {item.label}
                  </Link>
                ))}
              </div>
            </section>
            <p className="text-xs text-muted-foreground border-t pt-4">
              Workspace membership and organization permissions determine which
              records you can view and edit.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
