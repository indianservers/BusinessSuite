import { Link, useLocation } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuthStore } from "@/store/authStore";
import { getRequiredPermissionForPath, getRoleLabel } from "@/lib/roles";
import { getDefaultPathForUser } from "@/lib/products";

export default function AccessDeniedPage() {
  const location = useLocation();
  const { user } = useAuthStore();
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);
  const home = getDefaultPathForUser(user?.role, user?.is_superuser);

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-xl border-destructive/30">
        <CardContent className="space-y-6 p-8">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-destructive">403 Access Denied</p>
              <h1 className="mt-1 text-2xl font-semibold text-foreground">You do not have permission to open this page.</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                This route is protected by role-based access control.
              </p>
            </div>
          </div>

          <div className="rounded-lg border bg-background p-4 text-sm">
            <div className="grid gap-3 sm:grid-cols-[150px_1fr]">
              <span className="font-medium text-muted-foreground">Role</span>
              <span className="text-foreground">{roleLabel}</span>
              <span className="font-medium text-muted-foreground">Requested Page</span>
              <span className="break-all text-foreground">{location.pathname}</span>
              <span className="font-medium text-muted-foreground">Required Permission</span>
              <span className="text-foreground">{getRequiredPermissionForPath(location.pathname)}</span>
            </div>
          </div>

          <Button asChild>
            <Link to={home}>Return Home</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
