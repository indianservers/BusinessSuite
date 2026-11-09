import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure, MobileSheet } from "@/components/mobile/MobilePrimitives";
import { SmartCreateModal } from "@/shared/creation/SmartCreateModal";
import "./documents-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { ImportWizard } from "@/shared/data-transfer";
import { certificateImportFields } from "@/shared/data-transfer/fields";
import { FormEvent, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, RefreshCw, Upload, ShieldCheck, FileSpreadsheet, Search, UserRound } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { companyApi, documentsApi, employeeApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { assetUrl, formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { getRoleKey } from "@/lib/roles";
import { Link, useSearchParams } from "react-router-dom";

type EmployeeOption = {
  id: number;
  employee_id: string;
  first_name: string;
  last_name: string;
  personal_email?: string | null;
  phone_number?: string | null;
  department_id?: number | null;
  branch_id?: number | null;
};

type EmployeeListResponse = {
  items: EmployeeOption[];
  total: number;
  page: number;
  per_page: number;
};

type BranchOption = { id: number; name: string };
type DepartmentOption = { id: number; name: string };

type Certificate = {
  id: number;
  employee_id: number;
  category: string;
  certificate_type: string;
  title: string;
  original_filename?: string | null;
  file_url: string;
  verification_status: string;
  uploaded_at?: string | null;
  verifier_name?: string | null;
  verifier_company?: string | null;
};

const categories = ["Study", "Class Certificate", "Old Company", "Identity", "Training", "Other"];

function apiError(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Request failed";
}

export default function DocumentsPage() {
  const qc = useQueryClient();
  const phone = useMobile(480);
  const [uploadOpen, setUploadOpen] = useState(false);
  const uploadOpener = useRef<HTMLButtonElement | null>(null);
  const [chooserOpen, setChooserOpen] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [verifyError, setVerifyError] = useState("");
  const [params] = useSearchParams();
  const { user } = useAuthStore();
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const grants=user?.access?.grants.hrms;
  const canChooseEmployee = !!user?.is_superuser || (user?.access ? !!grants?.enabled && grants.permissions.includes("employee_view") : ["admin", "hr"].includes(roleKey));
  const canUpload=!!user?.is_superuser || !user?.access || !!grants?.enabled && grants.actions.includes("create");
  const canVerify=!!user?.is_superuser || (user?.access ? !!grants?.enabled && grants.actions.includes("edit") && grants.permissions.includes("employee_update") : ["admin", "hr"].includes(roleKey));
  const [employeeId, setEmployeeId] = useState(params.get("employee_id") || (user?.employee_id ? String(user.employee_id) : ""));
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [branchId, setBranchId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [employeePage, setEmployeePage] = useState(1);
  const [category, setCategory] = useState("Study");
  const [certificateType, setCertificateType] = useState("Class 10");
  const [title, setTitle] = useState("");
  const [issuingEntity, setIssuingEntity] = useState("");
  const [certificateNumber, setCertificateNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const employeeFilters = {
    search: employeeSearch.trim() || undefined,
    branch_id: branchId || undefined,
    department_id: departmentId || undefined,
    page: employeePage,
    per_page: 20,

  };

  const employees = useQuery({
    queryKey: ["documents-employees", employeeFilters],
    queryFn: () => employeeApi.list(employeeFilters).then((r) => r.data as EmployeeListResponse),
    enabled: canChooseEmployee,
  });

  const branches = useQuery({
    queryKey: ["document-branches"],
    queryFn: () => companyApi.listBranches().then((r) => r.data as BranchOption[]),
    enabled: canChooseEmployee,
  });

  const departments = useQuery({
    queryKey: ["document-departments", branchId],
    queryFn: () => companyApi.listDepartments(branchId ? Number(branchId) : undefined).then((r) => r.data as DepartmentOption[]),
    enabled: canChooseEmployee,
  });

  const effectiveEmployeeId = employeeId || (user?.employee_id ? String(user.employee_id) : "");

  const certificates = useQuery({
    queryKey: ["certificates", effectiveEmployeeId],
    queryFn: () =>
      documentsApi
        .certificates({ employee_id: effectiveEmployeeId || undefined })
        .then((r) => r.data as Certificate[]),
    enabled: canChooseEmployee || Boolean(user?.employee_id),
  });

  const selectedEmployee = useMemo(
    () => employees.data?.items?.find((item) => String(item.id) === effectiveEmployeeId),
    [employees.data, effectiveEmployeeId]
  );

  const employeeTotal = employees.data?.total || 0;
  const employeeStart = employeeTotal ? (employeePage - 1) * 20 + 1 : 0;
  const employeeEnd = Math.min(employeePage * 20, employeeTotal);

  const uploadMutation = useMutation({
    onMutate: () => { if(phone)setUploadError(""); },
    mutationFn: () => {
      if (!effectiveEmployeeId) throw new Error("Select an employee first");
      if (!file) throw new Error("Choose a PDF or image file");
      const form = new FormData();
      form.append("employee_id", effectiveEmployeeId);
      form.append("category", category);
      form.append("certificate_type", certificateType);
      form.append("title", title || certificateType);
      if (issuingEntity) form.append("issuing_entity", issuingEntity);
      if (certificateNumber) form.append("certificate_number", certificateNumber);
      if (issueDate) form.append("issue_date", issueDate);
      if (expiryDate) form.append("expiry_date", expiryDate);
      form.append("file", file);
      return documentsApi.uploadCertificate(form);
    },
    onSuccess: () => {
      toast({ title: "Document uploaded" });
      if(phone)setUploadOpen(false);
      setTitle("");
      setCertificateNumber("");
      setIssueDate("");
      setExpiryDate("");
      setFile(null);
      qc.invalidateQueries({ queryKey: ["certificates"] });
    },
    onError: (error) => { if(phone)setUploadError(apiError(error)); toast({ title: "Upload failed", description: apiError(error), variant: "destructive" }); },
  });

  const verifyMutation = useMutation({
    onMutate: () => { if(phone)setVerifyError(""); },
    mutationFn: (id: number) =>
      documentsApi.verifyCertificate(id, {
        verification_status: "Verified",
        verifier_name: "Internal HR",
        verifier_company: "Company HR",
        verification_notes: "Verified from Documents page.",
      }),
    onSuccess: () => {
      toast({ title: "Certificate verified" });
      qc.invalidateQueries({ queryKey: ["certificates"] });
    },
    onError: (error) => { if(phone)setVerifyError(apiError(error)); toast({ title: "Verification failed", description: apiError(error), variant: "destructive" }); },
  });

  function submitUpload(event: FormEvent) {
    event.preventDefault();
    if(canUpload && !uploadMutation.isPending)uploadMutation.mutate();
  }

  const employeeChooser = (
<div className="space-y-2">
                  <Label>Employee</Label>
                  <div className="space-y-3 rounded-lg border p-3">
                    <div className="relative">
                      <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        aria-label={phone?"Search document employees":undefined} value={employeeSearch}
                        onChange={(event) => {
                          setEmployeeSearch(event.target.value);
                          setEmployeePage(1);
                        }}
                        placeholder="Search by name, employee ID, email, or phone"
                        className="pl-9"
                      />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <NativeSelect aria-label={phone?"Employee branch":undefined} loading={branches.isFetching} error={branches.isError}
                        value={branchId}
                        onChange={(event) => {
                          setBranchId(event.target.value);
                          setDepartmentId("");
                          setEmployeePage(1);
                        }}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      >
                        <option value="">All branches</option>
                        {branches.data?.map((branch) => (
                          <option key={branch.id} value={branch.id}>{branch.name}</option>
                        ))}
                      </NativeSelect>
                      <NativeSelect aria-label={phone?"Employee department":undefined} loading={departments.isFetching} error={departments.isError}
                        value={departmentId}
                        onChange={(event) => {
                          setDepartmentId(event.target.value);
                          setEmployeePage(1);
                        }}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      >
                        <option value="">All departments</option>
                        {departments.data?.map((department) => (
                          <option key={department.id} value={department.id}>{department.name}</option>
                        ))}
                      </NativeSelect>
                    </div>

                    {selectedEmployee && (
                      <div className="flex items-center gap-2 rounded-md bg-primary/10 px-3 py-2 text-sm text-primary">
                        <UserRound className="h-4 w-4" />
                        Selected: {selectedEmployee.first_name} {selectedEmployee.last_name} ({selectedEmployee.employee_id})
                      </div>
                    )}

                    {phone && employees.isError && <p role="alert">Could not load employees. <Button variant="outline" disabled={employees.isFetching} onClick={() => void employees.refetch()}>Retry document employees</Button></p>}{phone && branches.isError && <p role="alert">Could not load branches. <Button variant="outline" disabled={branches.isFetching} onClick={() => void branches.refetch()}>Retry document branches</Button></p>}{phone && departments.isError && <p role="alert">Could not load departments. <Button variant="outline" disabled={departments.isFetching} onClick={() => void departments.refetch()}>Retry document departments</Button></p>}<div className="max-h-64 overflow-y-auto rounded-md border">
                      {phone && employees.isError && !employees.data ? null : employees.isLoading ? (
                        <div className="p-3 text-sm text-muted-foreground">Searching employees...</div>
                      ) : employees.data?.items?.length ? (
                        employees.data.items.map((employee) => (
                          <button
                            key={employee.id}
                            type="button"
                            aria-pressed={String(employee.id)===effectiveEmployeeId} onClick={() => {setEmployeeId(String(employee.id));if(phone)setChooserOpen(false);}}
                            className={`flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left text-sm last:border-b-0 hover:bg-muted/50 ${
                              String(employee.id) === effectiveEmployeeId ? "bg-primary/10" : ""
                            }`}
                          >
                            <span className="min-w-0">
                              <span className="block truncate font-medium">
                                {employee.first_name} {employee.last_name}
                              </span>
                              <span className="block truncate text-xs text-muted-foreground">
                                {employee.employee_id}
                                {employee.personal_email ? ` - ${employee.personal_email}` : ""}
                                {employee.phone_number ? ` - ${employee.phone_number}` : ""}
                              </span>
                            </span>
                            <Badge variant="outline">Select</Badge>
                          </button>
                        ))
                      ) : (
                        <div className="p-3 text-sm text-muted-foreground">No employees match the current search.</div>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{phone && !employees.data ? employees.isLoading ? "Loading employee count…" : "Employee count unavailable." : employeeTotal ? `${employeeStart}-${employeeEnd} of ${employeeTotal}` : "No employees"}</span>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={employeePage <= 1 || phone && employees.isFetching}
                          onClick={() => setEmployeePage((page) => Math.max(1, page - 1))}
                        >
                          Previous
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={employeeEnd >= employeeTotal || phone && employees.isFetching}
                          onClick={() => setEmployeePage((page) => page + 1)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
  );
  const issuingFields = (
<div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Issuing entity</Label>
                  <Input disabled={phone && uploadMutation.isPending} aria-label="Issuing entity" value={issuingEntity} onChange={(event) => setIssuingEntity(event.target.value)} placeholder="CBSE, University, Previous company" />
                </div>
                <div className="space-y-2">
                  <Label>Certificate number</Label>
                  <Input disabled={phone && uploadMutation.isPending} aria-label="Certificate number" value={certificateNumber} onChange={(event) => setCertificateNumber(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Issue date</Label>
                  <Input disabled={phone && uploadMutation.isPending} aria-label={phone?"Issue date":undefined} type="date" value={issueDate} onChange={(event) => setIssueDate(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Expiry date</Label>
                  <Input disabled={phone && uploadMutation.isPending} aria-label={phone?"Expiry date":undefined} type="date" value={expiryDate} onChange={(event) => setExpiryDate(event.target.value)} />
                </div>
              </div>
  );
  const uploadEditor = (
<Card className="hrms-document-upload">
          <CardHeader>
            <CardTitle className="text-base">Upload softcopy</CardTitle>
            <CardDescription>Allowed files: PDF, DOC, DOCX, JPG, JPEG, PNG</CardDescription>
          </CardHeader>
          <CardContent>
            <CompactForm compactTabs={phone?false:undefined} className="space-y-4" onSubmit={submitUpload}>
              {canChooseEmployee && (phone ? <p className="text-sm">Employee: {selectedEmployee ? `${selectedEmployee.first_name} ${selectedEmployee.last_name} (${selectedEmployee.employee_id})` : effectiveEmployeeId ? `#${effectiveEmployeeId}` : "Select an employee before uploading."}</p> : employeeChooser)}

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Category</Label>
                  <NativeSelect disabled={phone && uploadMutation.isPending}
                    aria-label={phone?"Document category":undefined} value={category}
                    onChange={(event) => setCategory(event.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    {categories.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </NativeSelect>
                </div>
                <div className="space-y-2">
                  <Label>Certificate type</Label>
                  <Input disabled={phone && uploadMutation.isPending} aria-label="Certificate type" value={certificateType} onChange={(event) => setCertificateType(event.target.value)} required />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Title</Label>
                <Input disabled={phone && uploadMutation.isPending}
                  aria-label="Document title" value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Class 10 marksheet, degree certificate, relieving letter..."
                />
              </div>

{phone ? <MobileDisclosure maxWidth={480} title="Issuing details & dates">{issuingFields}</MobileDisclosure> : issuingFields}
              <div className="space-y-2">
                <Label>File</Label>
                <Input disabled={phone && uploadMutation.isPending}
                  type="file" aria-label="Certificate file"
                  accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                  required
                />
              </div>

              {phone && uploadError && <p role="alert" className="text-sm text-destructive">{uploadError}</p>}<Button aria-busy={phone && uploadMutation.isPending || undefined} data-save-action type="submit" disabled={!canUpload || uploadMutation.isPending || !effectiveEmployeeId}>
                <Upload className="h-4 w-4" />
                {uploadMutation.isPending ? "Uploading..." : "Upload document"}
              </Button>
            </CompactForm>
          </CardContent>
        </Card>
  );

  return (
    <div className="hrms-documents space-y-5">
      <div className="hrms-document-header flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Documents</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Employee certificates and documents</h1>
          {canChooseEmployee && <Link className="mt-2 inline-block text-sm font-medium text-primary underline" to="/hrms/letters-certificates">Generate letters & certificates</Link>}
          <p className="mt-1 text-sm text-muted-foreground">
            Upload study certificates, class certificates, old company documents, and verification evidence.
          </p>
        </div>
        <Button aria-label="Refresh" disabled={phone && (certificates.isFetching || !canChooseEmployee && !user?.employee_id)} variant="outline" onClick={() => certificates.refetch()}>
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </Button>
      </div>

      {!canChooseEmployee && !user?.employee_id && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-4 text-sm text-amber-900">
            Your login is missing an employee profile id. Please log out and sign in again, then upload your documents here.
          </CardContent>
        </Card>
      )}

      {phone && canChooseEmployee && <section className="hrms-document-employee"><p className="text-sm">Documents for {selectedEmployee?`${selectedEmployee.first_name} ${selectedEmployee.last_name}`:effectiveEmployeeId?`employee #${effectiveEmployeeId}`:"an employee"}</p><Button variant="outline" onClick={() => setChooserOpen(true)}>Choose employee</Button><MobileSheet open={chooserOpen} title="Choose document employee" onClose={() => setChooserOpen(false)}><div className="hrms-document-chooser">{employeeChooser}</div></MobileSheet></section>}
      <div className="hrms-document-layout grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        {phone ? <><Button onClick={event => {uploadOpener.current=event.currentTarget;setUploadError("");setUploadOpen(true);}}><Upload className="h-4 w-4" />Upload document</Button>{uploadOpen && <SmartCreateModal definition={{entity:"hr-document",title:"Upload document",presentation:"page",size:"standard"}} mobileSheet returnFocus={uploadOpener.current} busy={uploadMutation.isPending} onClose={() => {setUploadOpen(false);setTitle("");setIssuingEntity("");setCertificateNumber("");setIssueDate("");setExpiryDate("");setCategory("Study");setCertificateType("Class 10");setFile(null);setUploadError("");}}>{uploadEditor}</SmartCreateModal>}</> : <SmartCreateSection title="Upload document" size="large">{uploadEditor}</SmartCreateSection>}

        <Card className="hrms-document-repository">
          <CardHeader>
            <CardTitle className="text-base">Uploaded documents</CardTitle>
            <CardDescription>
              {selectedEmployee ? `${selectedEmployee.first_name} ${selectedEmployee.last_name}` : "Employee certificate repository"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {phone && verifyError && <p role="alert" className="text-sm text-destructive">{verifyError}</p>}
            {phone && certificates.isError && <p role="alert">Documents could not load. <Button disabled={certificates.isFetching} variant="outline" onClick={() => void certificates.refetch()}>Retry documents</Button></p>}
            {phone && certificates.isError && !certificates.data ? null : certificates.isLoading ? (
              <div role={phone?"status":undefined} aria-label={phone?"Loading documents":undefined} className="h-24 rounded-lg border bg-muted/30" />
            ) : certificates.data?.length ? (
              <GroupedRecords scope="apps/hrms/pages/documents/DocumentsPage:records-1" items={(certificates.data) || []} fields={standardRecordGroups((certificates.data) || [])} gridClassName="space-y-3" renderItem={(item) => (
                <div key={item.id} className="hrms-document-record flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.title}</p>
                        <Badge variant={item.verification_status === "Verified" ? "success" : "warning"}>
                          {item.verification_status}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {item.category} • {item.certificate_type} • {formatDate(item.uploaded_at || null)}
                      </p>
                      {item.original_filename && (
                        <a className="mt-1 block text-sm text-primary underline-offset-4 hover:underline" href={assetUrl(item.file_url)} target="_blank" rel="noreferrer">
                          {item.original_filename}
                        </a>
                      )}
                    </div>
                  </div>
                  {canVerify && item.verification_status !== "Verified" && (
                    <Button variant="outline" size="sm" disabled={verifyMutation.isPending} onClick={() => verifyMutation.mutate(item.id)}>
                      <ShieldCheck className="h-4 w-4" />
                      Verify
                    </Button>
                  )}
                </div>
              )}/>
            ) : (
              <p className="rounded-lg border p-4 text-sm text-muted-foreground">No documents uploaded yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {canChooseEmployee && (
        <MobileDisclosure maxWidth={480} title="Bulk import"><Card>
          <CardHeader>
            <CardTitle className="text-base">Bulk import</CardTitle>
            <CardDescription>Map Excel or CSV columns and upload a certificate import batch.</CardDescription>
          </CardHeader>
          <CardContent><ImportWizard title="Prepare certificate import" label="Import spreadsheet" fields={certificateImportFields} onImport={async({file})=>{const form=new FormData();if(effectiveEmployeeId)form.append("employee_id",effectiveEmployeeId);form.append("remarks","Mapped certificate import from Documents page");form.append("file",file);await documentsApi.importCertificates(form);return {message:"Mapped file uploaded as a certificate import batch. It is queued for processing; certificates have not been created by this upload."};}}/></CardContent>
        </Card></MobileDisclosure>
      )}
    </div>
  );
}
