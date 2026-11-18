import { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import MobileModuleDock from "../../src/components/layout/MobileModuleDock";
import SharedDataGrid from "../../src/shared/data-grid/SharedDataGrid";
import { localGridSource } from "../../src/shared/data-grid/local-source";
import GridTable from "../../src/shared/data-grid/GridTable";
import type { GridColumn } from "../../src/shared/data-grid/types";
import { NativeSelect } from "../../src/components/ui/native-select";
import { useRecordDraft } from "../../src/hooks/use-record-autosave";
import SuiteNotificationsPage from "../../src/pages/SuiteNotificationsPage";
import AddEmployeePage from "../../src/apps/hrms/pages/employees/AddEmployeePage";
import { CreationDialogEnhancements } from "../../src/shared/creation/CreationDialogEnhancements";
import { useAuthStore } from "../../src/store/authStore";
import "../../src/index.css";
import "../../src/design-system/premium.css";

const params = new URLSearchParams(location.search), screen = params.get("screen");
const restricted = params.has("restricted");
useAuthStore.setState({ isHydrated: true, isAuthenticated: true, accessToken: "fixture", user: { id: 55, email: "mobile@example.test", role: restricted ? "member" : "admin", is_superuser: !restricted, access: { managed: true, companyId: 1, companyName: "Mobile test company", organizations: [{ id: 1, name: "Mobile test company" }], memberships: [1], isAccessAdmin: !restricted, isGlobalAdmin: !restricted, companyDisabledModules: [], modules: ["crm", "pms", "srm", "hrms"].map(key => ({ key: key === "pms" ? "project_management" : key, route: `/${key}`, label: key.toUpperCase() })), grants: Object.fromEntries(["crm", "hrms", "srm", "project_management"].map(key => [key, { enabled: true, role: restricted ? "member" : "admin", scope: "company", permissions: restricted ? [] : ["reports_view", "employee_create", "crm_leads_manage"], actions: restricted ? ["view"] : ["view", "create", "edit", "assign"] }])) } } });
type Row = { id: string; name: string; owner_user_id: number | null; due_date: string; status: string; email: string; phone: string; notes: string; extra: string };
const now = new Date(), today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
const columns: GridColumn<Row>[] = [
  { id: "name", title: "Name", editable: true }, { id: "owner_user_id", title: "Owner", type: "owner" }, { id: "due_date", title: "Due date", type: "date" },
  { id: "status", title: "Status", type: "status", options: [{ value: "Open", label: "Open" }, { value: "Completed", label: "Completed" }, { value: "Pending approval", label: "Pending approval" }] },
  { id: "email", title: "Email" }, { id: "phone", title: "Phone" }, { id: "notes", title: "Notes" }, { id: "extra", title: "Extra details" },
];
function Records() {
  const [rows, setRows] = useState<Row[]>([
    { id: "1", name: "Launch campaign", owner_user_id: 55, due_date: today, status: "Open", email: "customer@example.test", phone: "+919876543210", notes: "Keep customer informed", extra: "More context" },
    { id: "2", name: "Review proposal", owner_user_id: null, due_date: "2020-01-01", status: "Pending approval", email: "review@example.test", phone: "+919876543211", notes: "Awaiting review", extra: "Second record" },
    { id: "3", name: "Finished work", owner_user_id: 55, due_date: "2020-01-01", status: "Completed", email: "done@example.test", phone: "+919876543212", notes: "Complete", extra: "Closed record" },
  ]);
  const [opened, setOpened] = useState("");
  const source = useMemo(() => { const local = localGridSource("mobile-usability", rows, columns, row => row.id); return { ...local, load: async (...args: Parameters<typeof local.load>) => ({ ...await local.load(...args), permissions: { edit: true, assign: true, export: true } }) }; }, [rows]);
  return <><output aria-label="Opened record">{opened}</output><SharedDataGrid personalViews={false} gridId="mobile-usability" title="Your tasks" columns={columns} dataSource={source} getRowId={row => row.id} overview={false} initialLayout={{ view: "grid", visibility: {} }} onOpen={row => setOpened(row.id)} onEdit={async (row, column, value) => { setRows(current => current.map(item => item.id === row.id ? { ...item, [column]: value } : item)); }} rowActions={[{ id: "start", label: "Start task", icon: CheckCircle2, quick: true, run: async row => { setOpened(`started:${row.id}`); } }]} bulkActions={[{ id: "assign", label: "Assign to me", run: async selected => { setRows(current => current.map(row => selected.some(item => item.id === row.id) ? { ...row, owner_user_id: 55 } : row)); } }]} /></>;
}
function DraftForm() {
  const [value, setValue] = useState({ name: "", email: "" });
  const draft = useRecordDraft("mobile-usability", value, setValue, true);
  return <form><p role="status">{draft.status}</p><label>Name<input value={value.name} onChange={e => setValue(current => ({ ...current, name: e.target.value }))} /></label><label>Email<input type="email" value={value.email} onChange={e => setValue(current => ({ ...current, email: e.target.value }))} /></label><label>Employee<NativeSelect aria-label="Employee" searchable>{Array.from({ length: 12 }, (_, i) => <option key={i} value={i}>Employee {i+1}</option>)}</NativeSelect></label><button type="button" onClick={draft}>Clear draft</button></form>;
}
function NativeRecords() {
  const [selected, setSelected] = useState(false), [approved, setApproved] = useState(false), [opened, setOpened] = useState(false);
  return <><output aria-label="Native selection">{String(selected)}</output><output aria-label="Native approval">{String(approved)}</output><output aria-label="Native open">{String(opened)}</output><GridTable gridId="mobile-native-actions" personalViews={false}><thead><tr><th>Select</th><th>Request</th><th>Status</th><th>Actions</th></tr></thead><tbody><tr key="request-1" onClick={() => setOpened(true)}><td><input type="checkbox" aria-label="Select native request" checked={selected} onChange={event => setSelected(event.target.checked)} /></td><td>Travel request</td><td>Pending approval</td><td><button type="button" onClick={() => setApproved(true)}>Approve request</button></td></tr></tbody></GridTable></>;
}
function App() {
  const route = useLocation();
  return <><CreationDialogEnhancements /><main id="suite-main" className="kf-main min-h-screen bg-background p-3 pb-40"><h1 className="mb-3 text-xl font-semibold">Mobile workspace</h1><output className="sr-only" aria-label="Current route">{route.pathname}{route.search}{route.hash}</output>{screen === "grid" ? <Records /> : screen === "native" ? <NativeRecords /> : screen === "draft" ? <DraftForm /> : screen === "employee" ? <AddEmployeePage /> : screen === "notifications" ? <SuiteNotificationsPage /> : <p className="text-sm text-muted-foreground">Your work, wherever you are.</p>}</main><MobileModuleDock /></>;
}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter initialEntries={[params.get("route") || "/pms/tasks"]}><App /></MemoryRouter></QueryClientProvider>);
