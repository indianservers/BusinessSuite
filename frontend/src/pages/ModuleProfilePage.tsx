import { Mail, ShieldCheck, UserCircle } from "lucide-react";
import { useLocation } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/store/authStore";
import { getRoleLabel } from "@/lib/roles";
import { BUSINESS_SUITE_DISPLAY_NAME, getProductDisplayName, getProductForContext } from "@/lib/products";
import { usePageTitle } from "@/hooks/use-page-title";

export default function ModuleProfilePage() {
  const location = useLocation();
  const { user } = useAuthStore();
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);
  usePageTitle(`${product.shortName} Profile`);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">{product.shortName} Profile</h1>
        <p className="page-description">Your workspace identity and module access summary.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                <UserCircle className="h-8 w-8" />
              </div>
              <div>
                <p className="text-lg font-semibold">{user?.name || user?.email?.split("@")[0] || "User"}</p>
                <p className="text-sm text-muted-foreground">{user?.email}</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Module</p>
                <p className="mt-1 font-medium">{product.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{getProductDisplayName(product)}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Suite</p>
                <p className="mt-1 font-medium">{BUSINESS_SUITE_DISPLAY_NAME}</p>
              </div>
              <div className="rounded-lg border p-4 sm:col-span-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Role</p>
                <p className="mt-1 font-medium">{roleLabel}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Access Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center gap-3 rounded-lg border p-3">
              <Mail className="h-4 w-4 text-primary" />
              <span>{user?.email || "No email available"}</span>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-3">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <span>{user?.is_superuser ? "Super admin access" : "Standard module access"}</span>
            </div>
            <Badge variant="outline">{product.shortName} workspace</Badge>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
