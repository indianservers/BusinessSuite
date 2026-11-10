import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import SettingsPage, { type SettingKey } from "./SettingsPage";
import type { SettingsOption } from "@/pages/settings/SettingsDirectory";

const hrSections = new Set<SettingKey>(["departments", "designations", "shifts", "holidays", "leaveTypes", "salaryComponents"]);

export default function HRSettingsPage() {
  const { section } = useParams();
  const user = useAuthStore(state => state.user);
  const catalog = useQuery({
    queryKey: ["hr-module-settings", user?.id, user?.access?.companyId],
    queryFn: () => api.get<{ options: SettingsOption[] }>("/access/settings").then(response => response.data),
  });
  if (catalog.isPending) return <p role="status" className="p-6">Loading HR settings…</p>;
  if (catalog.isError) return <div className="p-6" role="alert">Could not load HR settings. <button onClick={() => void catalog.refetch()}>Try again</button></div>;
  const options = catalog.data.options.filter(option => hrSections.has(option.id as SettingKey));
  if (section) return <div className="space-y-4 p-4">
    <Link to="/hrms/settings" className="text-primary underline">Back to HR settings</Link>
    {options.some(option => option.id === section) ? <SettingsPage key={section} section={section as SettingKey} /> : <p role="alert">This HR setting is unavailable for your account.</p>}
  </div>;
  return <main className="space-y-5 p-4 sm:p-6">
    <header><h1 className="text-xl font-semibold">HR settings</h1><p className="text-sm text-muted-foreground">Set up your organization, work schedules, leave and payroll.</p></header>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{options.map(option => <Link key={option.id} to={`/hrms/settings/${option.id}`} className="rounded-xl border p-4 hover:bg-muted focus-visible:outline focus-visible:outline-2">
      <h2 className="font-medium">{option.title}</h2><p className="mt-1 text-sm text-muted-foreground">{option.description}</p>
    </Link>)}</div>
    {!options.length && <p>No HR settings are available for your account.</p>}
  </main>;
}
