import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import SendReminders from "@/apps/communication/center/SendReminders";
import SalesCommunicationCenter from "./SalesCommunicationCenter";

export default function RemindersPage({ source }: { source: "crm" | "srm" }) {
  const user = useAuthStore(state => state.user);
  if (source === "srm") return <SalesCommunicationCenter />;
  return <main className="space-y-5">
    <header>
      <h1 className="text-2xl font-semibold">CRM Reminders</h1>
      <p className="text-sm text-muted-foreground">Review membership expiries and track renewal follow-ups.</p>
    </header>
    <div className="grid gap-2 sm:flex sm:flex-wrap">
      <Button asChild className="min-h-11"><Link to={`/${source}/membership-expiry`}>Membership Expiry Report</Link></Button>
      <Button asChild className="min-h-11" variant="outline"><Link to={`/${source}/follow-ups`}>Scheduled follow-ups</Link></Button>
    </div>
    {canAccessRoute("/crm/send-reminders", user?.role, user?.is_superuser) &&
      <div className="rounded-lg border bg-card p-4"><SendReminders embedded/></div>}
  </main>;
}
