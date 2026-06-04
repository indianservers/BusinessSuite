import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CalendarDays,
  Clock,
  GripVertical,
  Layers3,
  MapPin,
  Plus,
  Search,
  ShieldCheck,
  Tags,
  X,
  Pencil,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { attendanceApi, authApi, companyApi, leaveApi, payrollApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

type Entity = Record<string, any>;
type SettingKey = "companies" | "branches" | "departments" | "designations" | "shifts" | "holidays" | "leaveTypes" | "salaryComponents" | "roles";

const sections: { key: SettingKey; title: string; description: string; icon: any }[] = [
  { key: "companies", title: "Companies", description: "Legal entities and statutory identity", icon: Building2 },
  { key: "branches", title: "Branches", description: "Offices, locations, and contact points", icon: MapPin },
  { key: "departments", title: "Departments", description: "Business units for employee mapping", icon: Layers3 },
  { key: "designations", title: "Designations", description: "Titles, grades, and reporting levels", icon: Tags },
  { key: "shifts", title: "Shifts", description: "Work timings, grace, and night shift rules", icon: Clock },
  { key: "holidays", title: "Holidays", description: "Holiday calendars by year and branch", icon: CalendarDays },
  { key: "leaveTypes", title: "Leave Types", description: "Casual, sick, earned, maternity, comp-off rules", icon: CalendarDays },
  { key: "salaryComponents", title: "Salary Components", description: "Earnings, deductions, taxability, PF and ESI flags", icon: Tags },
  { key: "roles", title: "User Roles", description: "Admin, HR, manager, employee, and custom permissions", icon: ShieldCheck },
];

function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4">
      <div className="w-full max-w-2xl rounded-t-lg border bg-background shadow-2xl sm:rounded-lg">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-base font-semibold">{title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="max-h-[75vh] overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex min-h-52 flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 p-8 text-center">
      <ShieldCheck className="mb-3 h-9 w-9 text-muted-foreground/50" />
      <p className="font-medium">Nothing configured yet</p>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        Add setup data here and it will appear immediately in employee and workflow forms.
      </p>
      <Button className="mt-4" size="sm" onClick={onAdd}>
        <Plus className="mr-2 h-4 w-4" />
        Add first record
      </Button>
    </div>
  );
}

export default function SettingsPage() {
  usePageTitle("Settings");
  const qc = useQueryClient();
  const [active, setActive] = useState<SettingKey>("companies");
  const [query, setQuery] = useState("");
  const [modal, setModal] = useState<SettingKey | null>(null);
  const [editing, setEditing] = useState<Entity | null>(null);
  const [form, setForm] = useState<Entity>({});

  const companies = useQuery({ queryKey: ["companies"], queryFn: () => companyApi.listCompanies().then((r) => r.data) });
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => companyApi.listBranches().then((r) => r.data) });
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => companyApi.listDepartments().then((r) => r.data) });
  const designations = useQuery({ queryKey: ["designations"], queryFn: () => companyApi.listDesignations().then((r) => r.data) });
  const shifts = useQuery({ queryKey: ["shifts"], queryFn: () => attendanceApi.listShifts().then((r) => r.data) });
  const holidays = useQuery({ queryKey: ["holidays"], queryFn: () => attendanceApi.listHolidays().then((r) => r.data) });
  const leaveTypes = useQuery({ queryKey: ["leave-types"], queryFn: () => leaveApi.types().then((r) => r.data) });
  const salaryComponents = useQuery({ queryKey: ["salary-components"], queryFn: () => payrollApi.components().then((r) => r.data) });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => authApi.roles().then((r) => r.data) });
  const permissions = useQuery({ queryKey: ["permissions"], queryFn: () => authApi.permissions().then((r) => r.data) });

  const dataByKey: Record<SettingKey, Entity[]> = {
    companies: companies.data || [],
    branches: branches.data || [],
    departments: departments.data || [],
    designations: designations.data || [],
    shifts: shifts.data || [],
    holidays: holidays.data || [],
    leaveTypes: leaveTypes.data || [],
    salaryComponents: salaryComponents.data || [],
    roles: roles.data || [],
  };

  const activeSection = sections.find((s) => s.key === active)!;
  const ActiveIcon = activeSection.icon;

  const filteredRows = useMemo(() => {
    const needle = query.toLowerCase().trim();
    if (!needle) return dataByKey[active];
    return dataByKey[active].filter((row) =>
      [row.name, row.code, row.city, row.email, row.grade, row.holiday_type].filter(Boolean).join(" ").toLowerCase().includes(needle)
    );
  }, [active, dataByKey, query]);

  const createMutation = useMutation({
    mutationFn: async ({ type, payload, id }: { type: SettingKey; payload: Entity; id?: number }) => {
      if (id) return updateSetting(type, id, payload);
      if (type === "companies") return companyApi.createCompany(payload);
      if (type === "branches") return companyApi.createBranch(payload);
      if (type === "departments") return companyApi.createDepartment(payload);
      if (type === "designations") return companyApi.createDesignation(payload);
      if (type === "shifts") return attendanceApi.createShift(payload);
      if (type === "holidays") return attendanceApi.createHoliday(payload);
      if (type === "leaveTypes") return leaveApi.createType(payload);
      if (type === "salaryComponents") return payrollApi.createComponent(payload);
      return authApi.createRole(payload);
    },
    onSuccess: (_, { type }) => {
      toast({ title: "Setting saved" });
      const keyMap: Record<SettingKey, string[]> = {
        companies: ["companies"],
        branches: ["branches"],
        departments: ["departments"],
        designations: ["designations"],
        shifts: ["shifts"],
        holidays: ["holidays"],
        leaveTypes: ["leave-types"],
        salaryComponents: ["salary-components"],
        roles: ["roles"],
      };
      keyMap[type].forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
      setModal(null);
      setEditing(null);
      setForm({});
    },
    onError: (err: any) => {
      toast({
        title: "Could not save",
        description: apiError(err),
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ type, id }: { type: SettingKey; id: number }) => deleteSetting(type, id),
    onSuccess: (_, { type }) => {
      toast({ title: "Setting removed" });
      const keys: Record<SettingKey, string> = {
        companies: "companies",
        branches: "branches",
        departments: "departments",
        designations: "designations",
        shifts: "shifts",
        holidays: "holidays",
        leaveTypes: "leave-types",
        salaryComponents: "salary-components",
        roles: "roles",
      };
      qc.invalidateQueries({ queryKey: [keys[type]] });
    },
    onError: (err: any) => toast({ title: "Could not remove", description: apiError(err), variant: "destructive" }),
  });

  const openCreate = (type: SettingKey) => {
    setForm(defaultForm(type, dataByKey));
    setEditing(null);
    setModal(type);
  };

  const openEdit = (type: SettingKey, row: Entity) => {
    setEditing(row);
    setForm(toForm(type, row));
    setModal(type);
  };

  const save = (event: React.FormEvent) => {
    event.preventDefault();
    if (!modal) return;
    createMutation.mutate({ type: modal, payload: normalizePayload(modal, form), id: editing?.id });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-description">Configure setup masters used across employee, attendance, payroll, and approval forms.</p>
        </div>
        <Button onClick={() => openCreate(active)}>
          <Plus className="mr-2 h-4 w-4" />
          Add {activeSection.title.slice(0, -1)}
        </Button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        <div className="space-y-3">
          {sections.map((section, index) => {
            const Icon = section.icon;
            const isActive = active === section.key;
            return (
              <button
                key={section.key}
                draggable
                onDragStart={(e) => e.dataTransfer.setData("text/plain", section.key)}
                onClick={() => setActive(section.key)}
                className={`flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-all ${
                  isActive ? "border-primary bg-primary/5 shadow-sm" : "bg-card hover:bg-muted/40"
                }`}
              >
                <GripVertical className="h-4 w-4 text-muted-foreground/60" />
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-muted-foreground">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold">{section.title}</p>
                    <Badge variant="secondary">{dataByKey[section.key].length}</Badge>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{section.description}</p>
                </div>
                <span className="text-xs text-muted-foreground">{index + 1}</span>
              </button>
            );
          })}
        </div>

        <Card className="overflow-hidden">
          <div className="flex flex-col gap-3 border-b p-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                <ActiveIcon className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-semibold">{activeSection.title}</h2>
                <p className="text-sm text-muted-foreground">{activeSection.description}</p>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input value={query} onChange={(e) => setQuery(e.target.value)} className="pl-9 sm:w-64" placeholder="Search settings" />
              </div>
              <Button variant="outline" onClick={() => openCreate(active)}>
                <Plus className="mr-2 h-4 w-4" />
                New
              </Button>
            </div>
          </div>

          <CardContent className="p-0">
            {!filteredRows.length ? (
              <div className="p-4">
                <EmptyState onAdd={() => openCreate(active)} />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="w-8 px-4 py-3 text-left"></th>
                      <th className="px-4 py-3 text-left">Name</th>
                      <th className="px-4 py-3 text-left">Code / Type</th>
                      <th className="px-4 py-3 text-left">Parent / Location</th>
                      <th className="px-4 py-3 text-left">Details</th>
                          <th className="px-4 py-3 text-left">Status</th>
                          <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((row) => (
                      <tr key={row.id} className="border-t hover:bg-muted/30">
                        <td className="px-4 py-3 text-muted-foreground"><GripVertical className="h-4 w-4" /></td>
                        <td className="px-4 py-3 font-medium">{row.name}</td>
                        <td className="px-4 py-3">{row.code || row.holiday_type || row.grade || "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground">{parentText(active, row, dataByKey)}</td>
                        <td className="px-4 py-3 text-muted-foreground">{detailText(active, row)}</td>
                        <td className="px-4 py-3">
                          <Badge variant={row.is_active === false ? "outline" : "success"}>{row.is_active === false ? "Inactive" : "Active"}</Badge>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(active, row)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive"
                            title="Delete"
                            aria-label="Delete"
                            onClick={() => window.confirm("Delete this setting?") && deleteMutation.mutate({ type: active, id: row.id })}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {modal && (
        <Modal title={`${editing ? "Edit" : "Add"} ${sections.find((s) => s.key === modal)?.title.slice(0, -1)}`} onClose={() => setModal(null)}>
          <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
            {renderFields(modal, form, setForm, dataByKey, permissions.data || [])}
            <div className="flex justify-end gap-2 sm:col-span-2">
              <Button type="button" variant="outline" onClick={() => setModal(null)}>Cancel</Button>
              <Button type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? "Saving..." : "Save"}</Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

function defaultForm(type: SettingKey, data: Record<SettingKey, Entity[]>): Entity {
  if (type === "branches") return { country: "India", company_id: data.companies[0]?.id || "" };
  if (type === "departments") return { branch_id: data.branches[0]?.id || "" };
  if (type === "designations") return { department_id: data.departments[0]?.id || "", level: 1 };
  if (type === "shifts") return { start_time: "09:30", end_time: "18:30", grace_minutes: 10, working_hours: "8.0", is_night_shift: false };
  if (type === "holidays") return { holiday_type: "National" };
  if (type === "leaveTypes") return { days_allowed: 12, carry_forward: false, carry_forward_limit: 0, encashable: false, applicable_gender: "All", half_day_allowed: true, color: "#3B82F6" };
  if (type === "salaryComponents") return { component_type: "Earning", calculation_type: "Fixed", amount: 0, is_taxable: true, is_pf_applicable: false, is_esi_applicable: false };
  if (type === "roles") return { permission_ids: [] };
  return { country: "India" };
}

function normalizePayload(type: SettingKey, form: Entity) {
  const payload = { ...form };
  ["company_id", "branch_id", "department_id", "level", "grace_minutes"].forEach((key) => {
    if (payload[key] !== undefined && payload[key] !== "") payload[key] = Number(payload[key]);
  });
  ["days_allowed", "carry_forward_limit", "amount"].forEach((key) => {
    if (payload[key] !== undefined && payload[key] !== "") payload[key] = String(payload[key]);
  });
  if (type === "roles") {
    payload.permission_ids = (payload.permission_ids || []).map((id: string | number) => Number(id));
  }
  if (type === "shifts") payload.is_night_shift = Boolean(payload.is_night_shift);
  return payload;
}

function toForm(type: SettingKey, row: Entity) {
  if (type === "roles") return { ...row, permission_ids: (row.permissions || []).map((p: Entity) => p.id) };
  return { ...row };
}

function updateSetting(type: SettingKey, id: number, payload: Entity) {
  if (type === "companies") return companyApi.updateCompany(id, payload);
  if (type === "branches") return companyApi.updateBranch(id, payload);
  if (type === "departments") return companyApi.updateDepartment(id, payload);
  if (type === "designations") return companyApi.updateDesignation(id, payload);
  if (type === "shifts") return attendanceApi.updateShift(id, payload);
  if (type === "holidays") return attendanceApi.updateHoliday(id, payload);
  if (type === "leaveTypes") return leaveApi.updateType(id, payload);
  if (type === "salaryComponents") return payrollApi.updateComponent(id, payload);
  if (type === "roles") return authApi.updateRole(id, payload);
  return Promise.reject(new Error("Update not supported"));
}

function deleteSetting(type: SettingKey, id: number) {
  if (type === "branches") return companyApi.deleteBranch(id);
  if (type === "companies") return companyApi.deleteCompany(id);
  if (type === "departments") return companyApi.deleteDepartment(id);
  if (type === "designations") return companyApi.deleteDesignation(id);
  if (type === "shifts") return attendanceApi.deleteShift(id);
  if (type === "holidays") return attendanceApi.deleteHoliday(id);
  if (type === "leaveTypes") return leaveApi.deleteType(id);
  if (type === "salaryComponents") return payrollApi.deleteComponent(id);
  if (type === "roles") return authApi.deleteRole(id);
  return Promise.reject(new Error("Delete not supported for this setting"));
}

function apiError(err: any) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .filter(Boolean)
      .join("; ");
  }
  if (detail && typeof detail === "object") return detail.msg || detail.message || JSON.stringify(detail);
  return "Please check required fields";
}

function parentText(type: SettingKey, row: Entity, data: Record<SettingKey, Entity[]>) {
  if (type === "branches") return data.companies.find((c) => c.id === row.company_id)?.name || "-";
  if (type === "departments") return data.branches.find((b) => b.id === row.branch_id)?.name || "-";
  if (type === "designations") return data.departments.find((d) => d.id === row.department_id)?.name || "-";
  if (type === "companies") return [row.city, row.state].filter(Boolean).join(", ") || row.country || "-";
  if (type === "holidays") return row.holiday_date || "-";
  if (type === "leaveTypes") return `${row.days_allowed || 0} days`;
  if (type === "salaryComponents") return row.component_type || "-";
  if (type === "roles") return `${row.permissions?.length || 0} permissions`;
  return `${row.start_time || "-"} to ${row.end_time || "-"}`;
}

function detailText(type: SettingKey, row: Entity) {
  if (type === "companies" || type === "branches") return row.email || row.phone || row.website || "-";
  if (type === "departments" || type === "designations") return row.description || (row.level ? `Level ${row.level}` : "-");
  if (type === "shifts") return `${row.working_hours || 0} hrs, ${row.grace_minutes || 0} min grace`;
  if (type === "leaveTypes") return row.carry_forward ? `Carry forward up to ${row.carry_forward_limit || 0}` : "No carry forward";
  if (type === "salaryComponents") return `${row.calculation_type || "Fixed"} ${row.amount || ""}`;
  if (type === "roles") return row.description || (row.is_system ? "System role" : "Custom role");
  return row.description || "-";
}

function renderFields(type: SettingKey, form: Entity, setForm: (v: Entity) => void, data: Record<SettingKey, Entity[]>, permissions: Entity[]) {
  const update = (key: string, value: any) => setForm({ ...form, [key]: value });
  const text = (key: string, label: string, extra?: any) => (
    <Field key={key} label={label}><Input value={form[key] || ""} onChange={(e) => update(key, e.target.value)} {...extra} /></Field>
  );
  const select = (key: string, label: string, options: Entity[]) => (
    <Field key={key} label={label}>
      <select value={form[key] || ""} onChange={(e) => update(key, e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
        <option value="">Select</option>
        {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </Field>
  );

  if (type === "companies") return [text("name", "Company name *"), text("legal_name", "Legal name"), text("email", "Email"), text("phone", "Phone"), text("website", "Website"), text("city", "City"), text("state", "State"), text("pincode", "Pincode")];
  if (type === "branches") return [text("name", "Branch name *"), text("code", "Code"), select("company_id", "Company *", data.companies), text("email", "Email"), text("phone", "Phone"), text("city", "City"), text("state", "State"), text("pincode", "Pincode")];
  if (type === "departments") return [text("name", "Department name *"), text("code", "Code"), select("branch_id", "Branch *", data.branches), text("description", "Description")];
  if (type === "designations") return [text("name", "Designation name *"), text("code", "Code"), select("department_id", "Department *", data.departments), text("grade", "Grade"), text("level", "Level", { type: "number", min: 1 }), text("description", "Description")];
  if (type === "shifts") return [text("name", "Shift name *"), text("code", "Code"), text("start_time", "Start time *", { type: "time" }), text("end_time", "End time *", { type: "time" }), text("grace_minutes", "Grace minutes", { type: "number" }), text("working_hours", "Working hours", { type: "number", step: "0.5" })];
  if (type === "leaveTypes") return [
    text("name", "Leave type *"),
    text("code", "Code *"),
    text("days_allowed", "Days allowed", { type: "number", step: "0.5" }),
    text("carry_forward_limit", "Carry forward limit", { type: "number", step: "0.5" }),
    text("applicable_gender", "Applicable gender"),
    text("color", "Calendar color", { type: "color" }),
    <Field key="carry_forward" label="Carry forward"><input type="checkbox" checked={!!form.carry_forward} onChange={(e) => update("carry_forward", e.target.checked)} className="h-4 w-4" /></Field>,
    <Field key="encashable" label="Encashable"><input type="checkbox" checked={!!form.encashable} onChange={(e) => update("encashable", e.target.checked)} className="h-4 w-4" /></Field>,
  ];
  if (type === "salaryComponents") return [
    text("name", "Component name *"),
    text("code", "Code *"),
    <Field key="component_type" label="Type"><select value={form.component_type || "Earning"} onChange={(e) => update("component_type", e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"><option>Earning</option><option>Deduction</option><option>Benefit</option></select></Field>,
    <Field key="calculation_type" label="Calculation"><select value={form.calculation_type || "Fixed"} onChange={(e) => update("calculation_type", e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"><option>Fixed</option><option>Percentage</option><option>Formula</option></select></Field>,
    text("amount", "Default amount", { type: "number", step: "0.01" }),
    text("percentage_of", "Percentage of"),
    <Field key="is_taxable" label="Taxable"><input type="checkbox" checked={!!form.is_taxable} onChange={(e) => update("is_taxable", e.target.checked)} className="h-4 w-4" /></Field>,
    <Field key="is_pf_applicable" label="PF applicable"><input type="checkbox" checked={!!form.is_pf_applicable} onChange={(e) => update("is_pf_applicable", e.target.checked)} className="h-4 w-4" /></Field>,
  ];
  if (type === "roles") return [
    text("name", "Role name *"),
    text("description", "Description"),
    <div key="permissions" className="space-y-2 sm:col-span-2">
      <Label>Permissions</Label>
      <div className="grid max-h-72 gap-2 overflow-y-auto rounded-md border p-3 sm:grid-cols-2">
        {permissions.map((permission) => {
          const selected = (form.permission_ids || []).includes(permission.id);
          return (
            <label key={permission.id} className="flex items-center gap-2 rounded-md p-2 text-sm hover:bg-muted/50">
              <input
                type="checkbox"
                checked={selected}
                onChange={(e) => {
                  const ids = new Set(form.permission_ids || []);
                  e.target.checked ? ids.add(permission.id) : ids.delete(permission.id);
                  update("permission_ids", Array.from(ids));
                }}
              />
              <span>{permission.name}</span>
            </label>
          );
        })}
      </div>
    </div>,
  ];
  return [text("name", "Holiday name *"), text("holiday_date", "Date *", { type: "date" }), text("holiday_type", "Type"), text("description", "Description")];
}
