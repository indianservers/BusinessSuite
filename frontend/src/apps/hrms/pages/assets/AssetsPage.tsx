import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bike, Laptop, Package } from "lucide-react";
import { api, assetApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/utils";
import { usePageTitle } from "@/hooks/use-page-title";
import EmployeeSearchSelect from "../../components/EmployeeSearchSelect";

type Asset = { id: number; name: string; asset_tag: string; serial_number: string | null; status: string; category_id: number | null; warranty_expiry: string | null };
type Assignment = { id: number; asset_name: string; asset_tag: string; employee_id: number; employee_name: string; assigned_date: string; returned_date: string | null; acknowledged: boolean; condition_at_return: string | null; acknowledged_at?: string | null; remarks?: string | null };
type Clearance = { exit_id: number; employee_name: string; last_working_date: string | null; cleared: boolean; outstanding_assets: { assignment_id: number; name: string; asset_tag: string }[] };
const errorText = (error: unknown) => { const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail; return typeof detail === "string" ? detail : "Please check the details and try again."; };

export default function AssetsPage() {
  usePageTitle("Company assets");
  const qc = useQueryClient();
  const user = useAuthStore(s => s.user);
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("view") === "clearance" ? "clearance" : "inventory");
  const [search, setSearch] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [form, setForm] = useState({ name: "", asset_tag: "", serial_number: "", category_id: "", purchase_cost: "", description: "", purchase_date: "", warranty_expiry: "", brand: "", model: "" });
  const [conditions, setConditions] = useState<Record<number, string>>({});
  const permissions = useQuery({ queryKey: ["asset-permissions", user?.id], queryFn: () => api.get<{ can_manage: boolean }>("/assets/capabilities").then(r => r.data) });
  const canManage = !!permissions.data?.can_manage;
  const assets = useQuery({ queryKey: ["assets", user?.id, search], queryFn: () => assetApi.list({ search: search || undefined }).then(r => r.data as Asset[]) });
  const available = useQuery({ queryKey: ["assets-available", user?.id], queryFn: () => assetApi.list({ status: "Available" }).then(r => r.data as Asset[]), enabled: canManage });
  const categories = useQuery({ queryKey: ["asset-categories"], queryFn: () => assetApi.categories().then(r => r.data as { id: number; name: string }[]) });
  const assignments = useQuery({ queryKey: ["asset-assignments", user?.id, tab], queryFn: () => api.get<Assignment[]>("/assets/assignments", { params: { active: tab !== "history" } }).then(r => r.data) });
  const clearance = useQuery({ queryKey: ["asset-clearance", user?.id], queryFn: () => api.get<Clearance[]>("/assets/exit-clearance").then(r => r.data), enabled: tab === "clearance" });
  const refresh = () => Promise.all(["assets", "assets-available", "asset-assignments", "asset-clearance", "employee-360", "my-team"].map(key => qc.invalidateQueries({ queryKey: [key] })));
  const operation = useMutation({ mutationFn: async ({ action, id }: { action: string; id?: number }) => {
    if (action === "create") return assetApi.create({ ...form, category_id: form.category_id ? Number(form.category_id) : undefined, purchase_cost: form.purchase_cost || undefined, purchase_date: form.purchase_date || undefined, warranty_expiry: form.warranty_expiry || undefined });
    if (action === "assign") return assetApi.assign({ asset_id: Number(assetId), employee_id: Number(employeeId), assigned_date: new Date().toLocaleDateString("en-CA"), condition_at_assignment: "Good" });
    if (action === "acknowledge") return api.put(`/assets/assignments/${id}/acknowledge`);
    if (action === "repair-complete") return assetApi.update(id!, { status: "Available", condition: "Good" });
    return assetApi.returnAsset(id!, conditions[id!] || "Good");
  }, onSuccess: (_, variables) => {
    toast({ title: variables.action === "return" ? "Asset returned; exit clearance updated" : "Asset record updated" });
    if (variables.action === "create") setForm({ name: "", asset_tag: "", serial_number: "", category_id: "", purchase_cost: "", description: "", purchase_date: "", warranty_expiry: "", brand: "", model: "" });
    if (variables.action === "assign") { setAssetId(""); setEmployeeId(""); }
    refresh();
  }, onError: error => toast({ title: "Asset update failed", description: errorText(error), variant: "destructive" }) });
  const [categoryName, setCategoryName] = useState("");
  const categoryMutation = useMutation({ mutationFn: () => assetApi.createCategory({ name: categoryName.trim() }), onSuccess: () => { setCategoryName(""); qc.invalidateQueries({ queryKey: ["asset-categories"] }); }, onError: error => toast({ title: "Could not add category", description: errorText(error), variant: "destructive" }) });
  const field = (key: keyof typeof form, label: string, required = false) => <label className="block space-y-1 text-sm">{label}<Input required={required} value={form[key]} type={key === "purchase_cost" ? "number" : key.endsWith("date") || key === "warranty_expiry" ? "date" : "text"} min={key === "purchase_cost" ? 0 : undefined} onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>;
  return <div className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Company assets</h1><p className="text-sm text-muted-foreground">Bikes, laptops, phones and equipment: handovers, custody, returns and exit clearance.</p></div><Button variant="outline" onClick={refresh}>Refresh</Button></header>
    <nav aria-label="Asset views" className="flex flex-wrap gap-2">{[["inventory", "Inventory"], ["custody", "Employee custody"], ["history", "Return history"], ["clearance", "Exit clearance"]].map(([id, label]) => <Button key={id} variant={tab === id ? "default" : "outline"} onClick={() => setTab(id)} aria-pressed={tab === id}>{label}</Button>)}</nav>
    {tab === "inventory" && <div className={`grid items-start gap-5 ${canManage ? "xl:grid-cols-[22rem_1fr]" : ""}`}>
      {canManage && <div className="space-y-5"><Card><CardHeader><CardTitle className="text-base">Register an asset</CardTitle></CardHeader><CardContent><form className="space-y-3" onSubmit={e => { e.preventDefault(); operation.mutate({ action: "create" }); }}>
        {field("name", "Asset name (e.g. Honda bike / Dell laptop)", true)}{field("asset_tag", "Unique company asset tag", true)}
        <label className="block text-sm">Category<select className="mt-1 h-10 w-full rounded-md border bg-background px-3" value={form.category_id} onChange={e => setForm({ ...form, category_id: e.target.value })}><option value="">Uncategorized</option>{categories.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        {field("brand", "Brand")}{field("model", "Model")}{field("serial_number", "Serial / vehicle registration number")}{field("purchase_cost", "Purchase cost")}{field("purchase_date", "Purchase date")}{field("warranty_expiry", "Warranty expiry")}{field("description", "Handover notes / accessories")}
        <Button disabled={operation.isPending}>Register asset</Button>
      </form><details className="mt-4"><summary className="cursor-pointer text-sm">Add category (Bike, Laptop, etc.)</summary><form className="mt-2 flex gap-2" onSubmit={e => { e.preventDefault(); categoryMutation.mutate(); }}><Input aria-label="New asset category" value={categoryName} onChange={e => setCategoryName(e.target.value)} required maxLength={100} /><Button disabled={!categoryName.trim() || categoryMutation.isPending}>Add</Button></form></details></CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">Assign to employee</CardTitle></CardHeader><CardContent className="space-y-3"><label className="block text-sm">Available asset<select className="mt-1 h-10 w-full rounded-md border bg-background px-3" value={assetId} onChange={e => setAssetId(e.target.value)}><option value="">Select available asset</option>{available.data?.map(a => <option key={a.id} value={a.id}>{a.name} ({a.asset_tag})</option>)}</select></label>
        {available.isError && <p role="alert" className="text-sm text-destructive">Available assets could not load. Use Refresh to retry.</p>}
        <EmployeeSearchSelect endpoint="/assets/employees" value={employeeId} onChange={setEmployeeId} /><p className="text-xs text-muted-foreground">Assign available equipment to active employees. Assets issued during notice remain part of exit clearance.</p><Button disabled={!assetId || !employeeId || operation.isPending} onClick={() => operation.mutate({ action: "assign" })}>Assign asset</Button>
      </CardContent></Card></div>}
      <Card><CardHeader><CardTitle className="text-base">Inventory</CardTitle></CardHeader><CardContent className="space-y-3"><Input aria-label="Search inventory" placeholder="Name, asset tag or registration / serial" value={search} onChange={e => setSearch(e.target.value)} />
        {assets.isPending && <p role="status">Loading inventory…</p>}{assets.isError && <p role="alert">Inventory could not load. Use Refresh to retry.</p>}
        {assets.data?.map(a => { const category = categories.data?.find(c => c.id === a.category_id)?.name || "Equipment"; const Icon = /bike|vehicle/i.test(category) ? Bike : /laptop|computer/i.test(category) ? Laptop : Package; return <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"><div className="flex items-center gap-3"><Icon className="h-5 w-5" /><div><p className="font-medium">{a.name}</p><p className="text-xs text-muted-foreground">{category} · {a.asset_tag} · {a.serial_number || "No serial recorded"}</p></div></div><div className="space-y-2"><Badge variant="outline">{a.status}</Badge>{a.warranty_expiry && <p className="text-xs text-muted-foreground">Warranty: {formatDate(a.warranty_expiry)}{a.warranty_expiry < new Date().toLocaleDateString("en-CA") ? " (expired)" : ""}</p>}{canManage && a.status === "Under Repair" && <Button size="sm" variant="outline" disabled={operation.isPending} onClick={() => operation.mutate({ action: "repair-complete", id: a.id })}>Repair complete: make available</Button>}</div></div>; })}
        {assets.data?.length === 0 && <p className="text-sm text-muted-foreground">No assets match this search.</p>}{assets.data?.length === 200 && <p className="text-sm text-muted-foreground">Showing 200 assets. Refine your search.</p>}
      </CardContent></Card></div>}
    {(tab === "custody" || tab === "history") && <Card><CardHeader><CardTitle className="text-base">{tab === "history" ? "Returned assets" : "Assigned equipment & handover"}</CardTitle></CardHeader><CardContent className="space-y-3">
      {assignments.isPending && <p role="status">Loading custody records…</p>}{assignments.isError && <p role="alert">Custody records could not load. Use Refresh to retry.</p>}
      {assignments.data?.map(row => <div key={row.id} className="flex flex-wrap justify-between gap-4 rounded-lg border p-4"><div><p className="font-medium">{row.asset_name} · {row.asset_tag}</p><Link className="text-sm underline" to={`/hrms/employees/${row.employee_id}`}>{row.employee_name}</Link><p className="text-xs text-muted-foreground">Assigned {formatDate(row.assigned_date)}{row.returned_date && ` · Returned ${formatDate(row.returned_date)} · ${row.condition_at_return}`}</p><Badge variant="outline">{row.acknowledged ? "Acknowledged" : "Awaiting employee acknowledgement"}</Badge>{row.acknowledged_at && <p className="text-xs text-muted-foreground">Acknowledged {formatDate(row.acknowledged_at)}</p>}{row.remarks && <p className="mt-2 break-words text-sm">Handover notes: {row.remarks}</p>}</div>
        {tab !== "history" && <div className="flex flex-wrap items-center gap-2">{user?.employee_id === row.employee_id && !row.acknowledged && <Button size="sm" variant="outline" disabled={operation.isPending} onClick={() => operation.mutate({ action: "acknowledge", id: row.id })}>Acknowledge receipt</Button>}{canManage && <><label className="text-xs">Return condition<select aria-label={`Return condition for ${row.asset_tag}`} className="ml-2 rounded border bg-background p-2" value={conditions[row.id] || "Good"} onChange={e => setConditions({ ...conditions, [row.id]: e.target.value })}>{["New", "Good", "Fair", "Poor", "Damaged"].map(c => <option key={c}>{c}</option>)}</select></label><Button size="sm" variant="outline" disabled={operation.isPending} onClick={() => operation.mutate({ action: "return", id: row.id })}>Record return</Button></>}</div>}
      </div>)}{assignments.data?.length === 0 && <p className="text-sm text-muted-foreground">No {tab === "history" ? "returned" : "assigned"} assets.</p>}
    </CardContent></Card>}
    {tab === "clearance" && <Card><CardHeader><CardTitle className="text-base">Exit asset clearance</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Exit closure is blocked until every company asset is returned. Damaged returns go to Under Repair.</p>
      {clearance.isPending && <p role="status">Loading exits…</p>}{clearance.isError && <p role="alert">Exit clearance could not load. Use Refresh to retry.</p>}
      {clearance.data?.map(row => <div key={row.exit_id} className="rounded-lg border p-4"><div className="flex flex-wrap justify-between gap-2"><p className="font-medium">{row.employee_name} · Last day {formatDate(row.last_working_date)}</p><Badge variant={row.cleared ? "success" : "warning"}>{row.cleared ? "Assets cleared" : `${row.outstanding_assets.length} awaiting return`}</Badge></div>{row.outstanding_assets.map(a => <p className="mt-2 text-sm" key={a.assignment_id}>{a.name} · {a.asset_tag}</p>)}{!row.cleared && <Button className="mt-3" variant="outline" onClick={() => setTab("custody")}>Open custody & returns</Button>}</div>)}{clearance.data?.length === 0 && <p>No active exits require clearance.</p>}
    </CardContent></Card>}
  </div>;
}
