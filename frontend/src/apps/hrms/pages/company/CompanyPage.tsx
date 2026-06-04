import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Edit3,
  Globe,
  Layers3,
  Mail,
  MapPin,
  Phone,
  Plus,
  Save,
  Trash2,
  Users2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/state";
import { companyApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

type OrgForm = Record<string, any>;
type OrgKind = "branch" | "department" | "designation";

const emptyCompany = { country: "India" };
const emptyBranch = { country: "India" };
const emptyDepartment = {};
const emptyDesignation = { level: 1 };

export default function CompanyPage() {
  usePageTitle("Company");
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<OrgForm>(emptyCompany);
  const [branchForm, setBranchForm] = useState<OrgForm>(emptyBranch);
  const [departmentForm, setDepartmentForm] = useState<OrgForm>(emptyDepartment);
  const [designationForm, setDesignationForm] = useState<OrgForm>(emptyDesignation);

  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => companyApi.listCompanies().then((r) => r.data),
  });

  const selected = (companies.data || []).find((c: any) => c.id === selectedId) || companies.data?.[0];
  const selectedCompanyId = selected?.id || form.id;

  const branches = useQuery({
    queryKey: ["branches", selectedCompanyId],
    enabled: Boolean(selectedCompanyId),
    queryFn: () => companyApi.listBranches(selectedCompanyId).then((r) => r.data),
  });

  const branchIds = useMemo(() => (branches.data || []).map((branch: any) => branch.id), [branches.data]);

  const departments = useQuery({
    queryKey: ["departments", branchIds.join(",")],
    enabled: branchIds.length > 0,
    queryFn: async () => {
      const responses = await Promise.all(branchIds.map((id: number) => companyApi.listDepartments(id)));
      return responses.flatMap((response) => response.data);
    },
  });

  const departmentIds = useMemo(() => (departments.data || []).map((dept: any) => dept.id), [departments.data]);

  const designations = useQuery({
    queryKey: ["designations", departmentIds.join(",")],
    enabled: departmentIds.length > 0,
    queryFn: async () => {
      const responses = await Promise.all(departmentIds.map((id: number) => companyApi.listDesignations(id)));
      return responses.flatMap((response) => response.data);
    },
  });

  useEffect(() => {
    if (selected) {
      setSelectedId(selected.id);
      setForm(selected);
      setBranchForm({ ...emptyBranch, company_id: selected.id });
      setDepartmentForm(emptyDepartment);
      setDesignationForm(emptyDesignation);
    }
  }, [selected?.id]);

  useEffect(() => {
    if (!departmentForm.branch_id && branches.data?.[0]) {
      setDepartmentForm((current) => ({ ...current, branch_id: branches.data[0].id }));
    }
  }, [branches.data, departmentForm.branch_id]);

  useEffect(() => {
    if (!designationForm.department_id && departments.data?.[0]) {
      setDesignationForm((current) => ({ ...current, department_id: departments.data[0].id }));
    }
  }, [departments.data, designationForm.department_id]);

  const saveCompany = useMutation({
    mutationFn: () => {
      const payload = cleanPayload(form);
      return form.id ? companyApi.updateCompany(form.id, payload) : companyApi.createCompany(payload);
    },
    onSuccess: () => {
      toast({ title: "Company details saved" });
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
    onError: (err: any) => toast({ title: "Could not save company", description: apiError(err), variant: "destructive" }),
  });

  const saveOrg = useMutation({
    mutationFn: ({ kind, data }: { kind: OrgKind; data: OrgForm }) => {
      const payload = cleanPayload(data);
      if (kind === "branch") {
        return data.id ? companyApi.updateBranch(data.id, payload) : companyApi.createBranch({ ...payload, company_id: selectedCompanyId });
      }
      if (kind === "department") {
        return data.id ? companyApi.updateDepartment(data.id, payload) : companyApi.createDepartment(payload);
      }
      return data.id ? companyApi.updateDesignation(data.id, payload) : companyApi.createDesignation(payload);
    },
    onSuccess: (_, variables) => {
      toast({ title: `${titleFor(variables.kind)} saved` });
      resetOrgForm(variables.kind);
      invalidateOrg();
    },
    onError: (err: any) => toast({ title: "Could not save record", description: apiError(err), variant: "destructive" }),
  });

  const deleteOrg = useMutation({
    mutationFn: ({ kind, id }: { kind: OrgKind; id: number }) => {
      if (kind === "branch") return companyApi.deleteBranch(id);
      if (kind === "department") return companyApi.deleteDepartment(id);
      return companyApi.deleteDesignation(id);
    },
    onSuccess: (_, variables) => {
      toast({ title: `${titleFor(variables.kind)} deactivated` });
      invalidateOrg();
    },
    onError: (err: any) => toast({ title: "Could not deactivate record", description: apiError(err), variant: "destructive" }),
  });

  const uploadLogo = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return companyApi.uploadLogo(selectedCompanyId, formData);
    },
    onSuccess: () => {
      toast({ title: "Company logo uploaded" });
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
    onError: (err: any) => toast({ title: "Could not upload logo", description: apiError(err), variant: "destructive" }),
  });

  const update = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const branchName = (id: number) => (branches.data || []).find((branch: any) => branch.id === id)?.name || "Branch";
  const departmentName = (id: number) => (departments.data || []).find((dept: any) => dept.id === id)?.name || "Department";

  function invalidateOrg() {
    qc.invalidateQueries({ queryKey: ["branches"] });
    qc.invalidateQueries({ queryKey: ["departments"] });
    qc.invalidateQueries({ queryKey: ["designations"] });
  }

  function resetOrgForm(kind: OrgKind) {
    if (kind === "branch") setBranchForm({ ...emptyBranch, company_id: selectedCompanyId });
    if (kind === "department") setDepartmentForm({ ...emptyDepartment, branch_id: branches.data?.[0]?.id });
    if (kind === "designation") setDesignationForm({ ...emptyDesignation, department_id: departments.data?.[0]?.id });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">Company</h1>
          <p className="page-description">Manage legal entities, branches, departments, and designations.</p>
        </div>
        <Button variant="outline" onClick={() => { setSelectedId(null); setForm(emptyCompany); }}>
          <Plus className="mr-2 h-4 w-4" />
          New Company
        </Button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        <div className="space-y-2">
          {companies.isLoading && <LoadingState label="Loading companies" />}
          {companies.isError && <ErrorState title="Could not load companies" description="Company records are required before branch and payroll setup can continue." />}
          {(companies.data || []).map((company: any) => (
            <button
              key={company.id}
              onClick={() => { setSelectedId(company.id); setForm(company); }}
              className={`w-full rounded-lg border p-4 text-left transition-colors ${company.id === form.id ? "border-primary bg-primary/5" : "bg-card hover:bg-muted/40"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="truncate font-semibold">{company.name}</p>
                <Badge variant={company.is_active ? "success" : "outline"}>{company.is_active ? "Active" : "Inactive"}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{company.city || company.email || company.phone || "Company profile"}</p>
            </button>
          ))}
          {!companies.isLoading && !companies.isError && !companies.data?.length && (
            <EmptyState title="No companies yet" description="Create the legal entity first, then add branches, departments and designations." />
          )}
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Building2 className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>{form.id ? "Update Company Details" : "Create Company"}</CardTitle>
                  <CardDescription>These details appear in letters, payslips, statutory forms, and reports.</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <form
                className="grid gap-4 sm:grid-cols-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  saveCompany.mutate();
                }}
              >
                <Field label="Company Name *"><Input value={form.name || ""} onChange={(e) => update("name", e.target.value)} /></Field>
                <Field label="Legal Name"><Input value={form.legal_name || ""} onChange={(e) => update("legal_name", e.target.value)} /></Field>
                <Field label="Registration Number"><Input value={form.registration_number || ""} onChange={(e) => update("registration_number", e.target.value)} /></Field>
                <Field label="PAN"><Input value={form.pan_number || ""} onChange={(e) => update("pan_number", e.target.value)} /></Field>
                <Field label="TAN"><Input value={form.tan_number || ""} onChange={(e) => update("tan_number", e.target.value)} /></Field>
                <Field label="GSTIN"><Input value={form.gstin || ""} onChange={(e) => update("gstin", e.target.value)} /></Field>
                <Field label="Email"><Input value={form.email || ""} onChange={(e) => update("email", e.target.value)} /></Field>
                <Field label="Phone"><Input value={form.phone || ""} onChange={(e) => update("phone", e.target.value)} /></Field>
                <Field label="Website"><Input value={form.website || ""} onChange={(e) => update("website", e.target.value)} /></Field>
                <Field label="City"><Input value={form.city || ""} onChange={(e) => update("city", e.target.value)} /></Field>
                <Field label="State"><Input value={form.state || ""} onChange={(e) => update("state", e.target.value)} /></Field>
                <Field label="Pincode"><Input value={form.pincode || ""} onChange={(e) => update("pincode", e.target.value)} /></Field>
                <div className="space-y-2 sm:col-span-2">
                  <Label>Address</Label>
                  <textarea value={form.address || ""} onChange={(e) => update("address", e.target.value)} rows={3} className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
                </div>
                <div className="grid gap-3 rounded-lg bg-muted/30 p-4 text-sm sm:col-span-2 sm:grid-cols-3">
                  <span className="flex min-w-0 items-center gap-2"><Mail className="h-4 w-4 shrink-0 text-muted-foreground" /><span className="truncate">{form.email || "No email"}</span></span>
                  <span className="flex min-w-0 items-center gap-2"><Phone className="h-4 w-4 shrink-0 text-muted-foreground" /><span className="truncate">{form.phone || "No phone"}</span></span>
                  <span className="flex min-w-0 items-center gap-2"><Globe className="h-4 w-4 shrink-0 text-muted-foreground" /><span className="truncate">{form.website || "No website"}</span></span>
                  <span className="flex min-w-0 items-center gap-2 sm:col-span-3"><MapPin className="h-4 w-4 shrink-0 text-muted-foreground" /><span className="truncate">{[form.address, form.city, form.state, form.pincode].filter(Boolean).join(", ") || "No address"}</span></span>
                </div>
                <div className="flex flex-col gap-3 rounded-lg border p-4 sm:col-span-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-md bg-muted">
                      {form.logo_url ? <img src={form.logo_url} alt="Company logo" className="h-full w-full object-contain" /> : <Building2 className="h-5 w-5 text-muted-foreground" />}
                    </div>
                    <div>
                      <p className="text-sm font-medium">Company logo</p>
                      <p className="text-xs text-muted-foreground">Used in payslips, letters, and reports</p>
                    </div>
                  </div>
                  <Label className="cursor-pointer rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted">
                    Upload logo
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      className="hidden"
                      disabled={!selectedCompanyId || uploadLogo.isPending}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) uploadLogo.mutate(file);
                      }}
                    />
                  </Label>
                </div>
                <div className="flex justify-end sm:col-span-2">
                  <Button type="submit" disabled={saveCompany.isPending || !form.name}>
                    <Save className="mr-2 h-4 w-4" />
                    {saveCompany.isPending ? "Saving..." : "Save Company"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {selectedCompanyId && (
            <div className="grid gap-5 xl:grid-cols-3">
              <OrgPanel
                title="Branches"
                icon={<MapPin className="h-5 w-5" />}
                items={branches.data || []}
                form={branchForm}
                fields={[
                  { key: "name", label: "Branch Name *", required: true },
                  { key: "code", label: "Code" },
                  { key: "city", label: "City" },
                  { key: "state", label: "State" },
                  { key: "phone", label: "Phone" },
                  { key: "email", label: "Email" },
                ]}
                summary={(item) => [item.city, item.state].filter(Boolean).join(", ") || item.code || "Branch"}
                onChange={(key, value) => setBranchForm((current) => ({ ...current, [key]: value }))}
                onEdit={(item) => setBranchForm(item)}
                onNew={() => resetOrgForm("branch")}
                onDelete={(id) => deleteOrg.mutate({ kind: "branch", id })}
                onSubmit={() => saveOrg.mutate({ kind: "branch", data: branchForm })}
                saving={saveOrg.isPending}
                loading={branches.isLoading}
                error={branches.isError}
              />
              <OrgPanel
                title="Departments"
                icon={<Layers3 className="h-5 w-5" />}
                items={departments.data || []}
                form={departmentForm}
                fields={[
                  { key: "branch_id", label: "Branch *", type: "select", options: branches.data || [], required: true },
                  { key: "name", label: "Department Name *", required: true },
                  { key: "code", label: "Code" },
                  { key: "description", label: "Description" },
                ]}
                summary={(item) => branchName(item.branch_id)}
                onChange={(key, value) => setDepartmentForm((current) => ({ ...current, [key]: value }))}
                onEdit={(item) => setDepartmentForm(item)}
                onNew={() => resetOrgForm("department")}
                onDelete={(id) => deleteOrg.mutate({ kind: "department", id })}
                onSubmit={() => saveOrg.mutate({ kind: "department", data: departmentForm })}
                saving={saveOrg.isPending}
                loading={departments.isLoading}
                error={departments.isError}
              />
              <OrgPanel
                title="Designations"
                icon={<Users2 className="h-5 w-5" />}
                items={designations.data || []}
                form={designationForm}
                fields={[
                  { key: "department_id", label: "Department *", type: "select", options: departments.data || [], required: true },
                  { key: "name", label: "Designation Name *", required: true },
                  { key: "code", label: "Code" },
                  { key: "grade", label: "Grade" },
                  { key: "level", label: "Level", type: "number" },
                  { key: "description", label: "Description" },
                ]}
                summary={(item) => `${departmentName(item.department_id)}${item.grade ? `, Grade ${item.grade}` : ""}`}
                onChange={(key, value) => setDesignationForm((current) => ({ ...current, [key]: value }))}
                onEdit={(item) => setDesignationForm(item)}
                onNew={() => resetOrgForm("designation")}
                onDelete={(id) => deleteOrg.mutate({ kind: "designation", id })}
                onSubmit={() => saveOrg.mutate({ kind: "designation", data: designationForm })}
                saving={saveOrg.isPending}
                loading={designations.isLoading}
                error={designations.isError}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OrgPanel({
  title,
  icon,
  items,
  form,
  fields,
  summary,
  onChange,
  onEdit,
  onNew,
  onDelete,
  onSubmit,
  saving,
  loading,
  error,
}: {
  title: string;
  icon: React.ReactNode;
  items: any[];
  form: OrgForm;
  fields: Array<{ key: string; label: string; type?: "text" | "number" | "select"; options?: any[]; required?: boolean }>;
  summary: (item: any) => string;
  onChange: (key: string, value: any) => void;
  onEdit: (item: any) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
  onSubmit: () => void;
  saving: boolean;
  loading?: boolean;
  error?: boolean;
}) {
  const hasMissingRequired = fields.some((field) => field.required && !form[field.key]);

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">{icon}</div>
            <div>
              <CardTitle className="text-base">{title}</CardTitle>
              <CardDescription>{items.length} active</CardDescription>
            </div>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onNew} title={`New ${title}`}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          {fields.map((field) => (
            <Field key={field.key} label={field.label}>
              {field.type === "select" ? (
                <select
                  value={form[field.key] || ""}
                  onChange={(event) => onChange(field.key, Number(event.target.value))}
                  disabled={!field.options?.length}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select</option>
                  {(field.options || []).map((option) => (
                    <option key={option.id} value={option.id}>{option.name}</option>
                  ))}
                </select>
              ) : (
                <Input
                  type={field.type || "text"}
                  value={form[field.key] || ""}
                  onChange={(event) => onChange(field.key, field.type === "number" ? Number(event.target.value) : event.target.value)}
                />
              )}
            </Field>
          ))}
          <Button type="submit" className="w-full" disabled={saving || hasMissingRequired}>
            <Save className="h-4 w-4" />
            {saving ? "Saving..." : form.id ? "Update" : "Add"}
          </Button>
        </form>

        <div className="space-y-2">
          {loading && <LoadingState label={`Loading ${title.toLowerCase()}`} />}
          {error && <ErrorState title={`Could not load ${title.toLowerCase()}`} />}
          {!loading && !error && items.map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{item.name}</p>
                <p className="truncate text-xs text-muted-foreground">{summary(item)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button type="button" variant="ghost" size="icon" onClick={() => onEdit(item)} title="Edit">
                  <Edit3 className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => window.confirm("Deactivate this record?") && onDelete(item.id)}
                  title="Deactivate"
                  aria-label="Deactivate"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
          {!loading && !error && items.length === 0 && (
            <EmptyState title={`No ${title.toLowerCase()} yet`} description="Add the first record using the form above." />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  const required = label.includes("*");
  return (
    <div className="space-y-2">
      <Label>
        {label.replace(" *", "")}
        {required && <span className="ml-1 text-destructive" aria-label="required">*</span>}
      </Label>
      {children}
    </div>
  );
}

function cleanPayload(data: OrgForm) {
  const payload = { ...data };
  Object.keys(payload).forEach((key) => {
    if (payload[key] === "") payload[key] = null;
  });
  return payload;
}

function titleFor(kind: OrgKind) {
  if (kind === "branch") return "Branch";
  if (kind === "department") return "Department";
  return "Designation";
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
  return "Please check fields";
}
