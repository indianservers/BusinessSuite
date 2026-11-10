import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./documents-mobile.css";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { ImportWizard } from "@/shared/data-transfer";
import { certificateImportFields } from "@/shared/data-transfer/fields";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, Search, UserRound } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, companyApi, documentsApi, employeeApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";
import { getRoleKey } from "@/lib/roles";
import { useSearchParams } from "react-router-dom";

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

const categories = [
  "Study",
  "Class Certificate",
  "Old Company",
  "Identity",
  "Training",
  "Professional",
  "Employment",
  "Contracts",
  "Compliance",
  "Other",
];

function apiError(error: unknown) {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data
      ?.detail || (error instanceof Error ? error.message : "Request failed")
  );
}

export default function DocumentUploadTools({
  mode = "upload",
}: {
  mode?: "upload" | "import";
}) {
  const qc = useQueryClient();
  const phone = useMobile(480);
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState("");
  const [params] = useSearchParams();
  const { user } = useAuthStore();
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const grants = user?.access?.grants.hrms;
  const canChooseEmployee =
    !!user?.is_superuser ||
    (user?.access
      ? !!grants?.enabled && grants.permissions.includes("employee_view")
      : ["admin", "hr"].includes(roleKey));
  const canUpload =
    !!user?.is_superuser ||
    !user?.access ||
    (!!grants?.enabled && grants.actions.includes("create"));
  const canVerify =
    !!user?.is_superuser ||
    (user?.access
      ? !!grants?.enabled &&
        grants.actions.includes("edit") &&
        grants.permissions.includes("employee_update")
      : ["admin", "hr"].includes(roleKey));
  const [employeeId, setEmployeeId] = useState(
    params.get("employee_id") ||
      (user?.employee_id ? String(user.employee_id) : ""),
  );
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [branchId, setBranchId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [employeePage, setEmployeePage] = useState(1);
  const [category, setCategory] = useState("Study");
  const [certificateType, setCertificateType] = useState("Class 10");
  const [title, setTitle] = useState("");
  const [issuingEntity, setIssuingEntity] = useState("");
  const [issuingEntityType, setIssuingEntityType] = useState("");
  const [classGrade, setClassGrade] = useState("");
  const [courseProgram, setCourseProgram] = useState("");
  const [certificateNumber, setCertificateNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [reminderDate, setReminderDate] = useState("");
  const [remarks, setRemarks] = useState("");
  const [replaceId, setReplaceId] = useState("");
  const [progress, setProgress] = useState(0);
  const [filePreview, setFilePreview] = useState("");
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setFilePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function chooseFiles(next: File[]) {
    const allowed = /\.(pdf|doc|docx|jpg|jpeg|png)$/i;
    if (
      next.some(
        (f) => !allowed.test(f.name) || !f.size || f.size > 20 * 1024 * 1024,
      )
    ) {
      setUploadError(
        "Choose non-empty PDF, Word or image files, up to 20 MB each (server limits also apply).",
      );
      return;
    }
    if (new Set(next.map((f) => `${f.name}:${f.size}`)).size !== next.length) {
      setUploadError("Remove duplicate files from this selection.");
      return;
    }
    setUploadError("");
    setFiles(next);
    setFile(next[0] || null);
  }

  const employeeFilters = {
    search: employeeSearch.trim() || undefined,
    branch_id: branchId || undefined,
    department_id: departmentId || undefined,
    page: employeePage,
    per_page: 20,
  };

  const employees = useQuery({
    queryKey: ["documents-employees", employeeFilters],
    queryFn: () =>
      employeeApi
        .list(employeeFilters)
        .then((r) => r.data as EmployeeListResponse),
    enabled: canChooseEmployee,
  });

  const branches = useQuery({
    queryKey: ["document-branches"],
    queryFn: () =>
      companyApi.listBranches().then((r) => r.data as BranchOption[]),
    enabled: canChooseEmployee,
  });

  const departments = useQuery({
    queryKey: ["document-departments", branchId],
    queryFn: () =>
      companyApi
        .listDepartments(branchId ? Number(branchId) : undefined)
        .then((r) => r.data as DepartmentOption[]),
    enabled: canChooseEmployee,
  });

  const effectiveEmployeeId =
    employeeId || (user?.employee_id ? String(user.employee_id) : "");

  const selectedEmployee = useMemo(
    () =>
      employees.data?.items?.find(
        (item) => String(item.id) === effectiveEmployeeId,
      ),
    [employees.data, effectiveEmployeeId],
  );

  const employeeTotal = employees.data?.total || 0;
  const employeeStart = employeeTotal ? (employeePage - 1) * 20 + 1 : 0;
  const employeeEnd = Math.min(employeePage * 20, employeeTotal);

  const uploadMutation = useMutation({
    onMutate: () => {
      if (phone) setUploadError("");
    },
    mutationFn: async () => {
      if (!effectiveEmployeeId) throw new Error("Select an employee first");
      const chosen = files.length ? files : file ? [file] : [];
      if (!chosen.length) throw new Error("Choose a PDF, Word or image file");
      if (chosen.length > 1 && certificateNumber)
        throw new Error(
          "Upload documents with unique certificate references individually, or clear the reference for a multi-file upload",
        );
      if (replaceId && chosen.length !== 1)
        throw new Error("Replace one document at a time");
      setProgress(0);
      const completed: File[] = [];
      try {
        for (const current of chosen) {
          const form = new FormData();
          form.append("employee_id", effectiveEmployeeId);
          form.append("category", category);
          form.append("certificate_type", certificateType);
          form.append("title", title || current.name);
          for (const [key, value] of Object.entries({
            issuing_entity: issuingEntity,
            issuing_entity_type: issuingEntityType,
            class_or_grade: classGrade,
            course_or_program: courseProgram,
            certificate_number: certificateNumber,
            issue_date: issueDate,
            expiry_date: expiryDate,
            reminder_date: reminderDate,
            remarks,
            replace_certificate_id: replaceId,
          }))
            if (value) form.append(key, value);
          form.append("file", current);
          await api.post("/documents/certificates", form, {
            onUploadProgress: (e) => {
              setProgress(
                Math.round(
                  ((completed.length + (e.total ? e.loaded / e.total : 0)) /
                    chosen.length) *
                    100,
                ),
              );
            },
          });
          completed.push(current);
        }
      } finally {
        setFiles(chosen.filter((f) => !completed.includes(f)));
        setFile(chosen.find((f) => !completed.includes(f)) || null);
        if (completed.length)
          void qc.invalidateQueries({ queryKey: ["vault-insights"] });
      }
    },
    onSuccess: () => {
      toast({ title: "Document uploaded" });
      setUploadError("");
      setProgress(100);
      if (fileInput.current) fileInput.current.value = "";
      setFiles([]);
      setReplaceId("");
      setTitle("");
      setCertificateNumber("");
      setIssueDate("");
      setExpiryDate("");
      setFile(null);
      qc.invalidateQueries({ queryKey: ["certificates"] });
    },
    onError: (error) => {
      setUploadError(apiError(error));
      toast({
        title: "Upload failed",
        description: apiError(error),
        variant: "destructive",
      });
    },
  });

  function submitUpload(event: FormEvent) {
    event.preventDefault();
    if (canUpload && !uploadMutation.isPending) uploadMutation.mutate();
  }

  const employeeChooser = (
    <div className="space-y-2">
      <Label>Employee</Label>
      <div className="space-y-3 rounded-lg border p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            aria-label="Search document employees"
            value={employeeSearch}
            onChange={(event) => {
              setEmployeeSearch(event.target.value);
              setEmployeePage(1);
            }}
            placeholder="Search by name, employee ID, email, or phone"
            className="pl-9"
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <NativeSelect
            aria-label={phone ? "Employee branch" : undefined}
            loading={branches.isFetching}
            error={branches.isError}
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
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label={phone ? "Employee department" : undefined}
            loading={departments.isFetching}
            error={departments.isError}
            value={departmentId}
            onChange={(event) => {
              setDepartmentId(event.target.value);
              setEmployeePage(1);
            }}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="">All departments</option>
            {departments.data?.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </NativeSelect>
        </div>

        {selectedEmployee && (
          <div className="flex items-center gap-2 rounded-md bg-primary/10 px-3 py-2 text-sm text-primary">
            <UserRound className="h-4 w-4" />
            Selected: {selectedEmployee.first_name} {selectedEmployee.last_name}{" "}
            ({selectedEmployee.employee_id})
          </div>
        )}

        {phone && employees.isError && (
          <p role="alert">
            Could not load employees.{" "}
            <Button
              variant="outline"
              disabled={employees.isFetching}
              onClick={() => void employees.refetch()}
            >
              Retry document employees
            </Button>
          </p>
        )}
        {phone && branches.isError && (
          <p role="alert">
            Could not load branches.{" "}
            <Button
              variant="outline"
              disabled={branches.isFetching}
              onClick={() => void branches.refetch()}
            >
              Retry document branches
            </Button>
          </p>
        )}
        {phone && departments.isError && (
          <p role="alert">
            Could not load departments.{" "}
            <Button
              variant="outline"
              disabled={departments.isFetching}
              onClick={() => void departments.refetch()}
            >
              Retry document departments
            </Button>
          </p>
        )}
        <div className="max-h-64 overflow-y-auto rounded-md border">
          {phone &&
          employees.isError &&
          !employees.data ? null : employees.isLoading ? (
            <div className="p-3 text-sm text-muted-foreground">
              Searching employees...
            </div>
          ) : employees.data?.items?.length ? (
            employees.data.items.map((employee) => (
              <button
                key={employee.id}
                type="button"
                aria-pressed={String(employee.id) === effectiveEmployeeId}
                onClick={() => {
                  setEmployeeId(String(employee.id));
                }}
                className={`flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left text-sm last:border-b-0 hover:bg-muted/50 ${
                  String(employee.id) === effectiveEmployeeId
                    ? "bg-primary/10"
                    : ""
                }`}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">
                    {employee.first_name} {employee.last_name}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {employee.employee_id}
                    {employee.personal_email
                      ? ` - ${employee.personal_email}`
                      : ""}
                    {employee.phone_number ? ` - ${employee.phone_number}` : ""}
                  </span>
                </span>
                <Badge variant="outline">Select</Badge>
              </button>
            ))
          ) : (
            <div className="p-3 text-sm text-muted-foreground">
              No employees match the current search.
            </div>
          )}
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {phone && !employees.data
              ? employees.isLoading
                ? "Loading employee count…"
                : "Employee count unavailable."
              : employeeTotal
                ? `${employeeStart}-${employeeEnd} of ${employeeTotal}`
                : "No employees"}
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={employeePage <= 1 || (phone && employees.isFetching)}
              onClick={() => setEmployeePage((page) => Math.max(1, page - 1))}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={
                employeeEnd >= employeeTotal || (phone && employees.isFetching)
              }
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
        <Input
          disabled={phone && uploadMutation.isPending}
          aria-label="Issuing entity"
          value={issuingEntity}
          onChange={(event) => setIssuingEntity(event.target.value)}
          placeholder="CBSE, University, Previous company"
        />
      </div>
      <div className="space-y-2">
        <Label>Certificate number</Label>
        <Input
          disabled={phone && uploadMutation.isPending}
          aria-label="Certificate number"
          value={certificateNumber}
          onChange={(event) => setCertificateNumber(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label>Issue date</Label>
        <Input
          disabled={phone && uploadMutation.isPending}
          aria-label="Issue date"
          type="date"
          value={issueDate}
          onChange={(event) => setIssueDate(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label>Expiry date</Label>
        <Input
          disabled={phone && uploadMutation.isPending}
          aria-label="Expiry date"
          type="date"
          value={expiryDate}
          onChange={(event) => setExpiryDate(event.target.value)}
        />
      </div>
    </div>
  );
  const uploadEditor = (
    <Card className="hrms-document-upload">
      <CardHeader>
        <CardTitle className="text-base">Upload softcopy</CardTitle>
        <CardDescription>
          Allowed files: PDF, DOC, DOCX, JPG, JPEG, PNG
        </CardDescription>
      </CardHeader>
      <CardContent>
        <CompactForm
          compactTabs={false}
          className="space-y-4"
          onSubmit={submitUpload}
        >
          {canChooseEmployee && (
            <details open={!effectiveEmployeeId}>
              <summary className="cursor-pointer text-sm font-medium">
                {selectedEmployee
                  ? `${selectedEmployee.first_name} ${selectedEmployee.last_name} · ${selectedEmployee.employee_id}`
                  : "Select employee"}
              </summary>
              {employeeChooser}
            </details>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Category</Label>
              <NativeSelect
                disabled={phone && uploadMutation.isPending}
                aria-label="Document category"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {categories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-2">
              <Label>Certificate type</Label>
              <Input
                disabled={phone && uploadMutation.isPending}
                aria-label="Certificate type"
                value={certificateType}
                onChange={(event) => setCertificateType(event.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Title</Label>
            <Input
              disabled={phone && uploadMutation.isPending}
              aria-label="Document title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Class 10 marksheet, degree certificate, relieving letter..."
            />
          </div>

          {phone ? (
            <MobileDisclosure maxWidth={480} title="Issuing details & dates">
              {issuingFields}
            </MobileDisclosure>
          ) : (
            issuingFields
          )}
          <div
            className="space-y-2 rounded-xl border border-dashed p-4"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (!uploadMutation.isPending)
                chooseFiles(Array.from(e.dataTransfer.files));
            }}
          >
            <Label>Files · choose or drag & drop</Label>
            <Input
              disabled={phone && uploadMutation.isPending}
              ref={fileInput}
              type="file"
              aria-label="Certificate file"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
              multiple={!replaceId}
              onChange={(event) =>
                chooseFiles(Array.from(event.target.files || []))
              }
              required={!files.length}
            />
          </div>

          <details className="rounded border p-3">
            <summary className="cursor-pointer text-sm">
              Additional certificate details
            </summary>
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                [
                  "Issuing entity type",
                  issuingEntityType,
                  setIssuingEntityType,
                ],
                ["Class / grade", classGrade, setClassGrade],
                ["Course / program", courseProgram, setCourseProgram],
              ].map(([label, value, set]) => (
                <label key={label as string} className="text-sm">
                  {label as string}
                  <Input
                    value={value as string}
                    onChange={(e) =>
                      (set as (v: string) => void)(e.target.value)
                    }
                  />
                </label>
              ))}
            </div>
          </details>
          {files.length > 0 && (
            <div>
              <p className="text-xs">{files.length} file(s) selected</p>
              {files.map((f) => (
                <p key={f.name} className="text-xs text-muted-foreground">
                  {f.name} · {Math.ceil(f.size / 1024)} KB
                </p>
              ))}
              {file?.type.startsWith("image/") && (
                <img
                  src={filePreview}
                  alt="Selected document preview"
                  className="max-h-40 rounded border"
                />
              )}
              {file?.type === "application/pdf" && (
                <a
                  href={filePreview}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary underline"
                >
                  Preview selected PDF
                </a>
              )}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">
              Reminder date
              <Input
                aria-label="Reminder date"
                type="date"
                value={reminderDate}
                onChange={(e) => setReminderDate(e.target.value)}
              />
            </label>
            {canVerify && (
              <label className="text-sm">
                Replace existing document ID (optional)
                <Input
                  aria-label="Replace document ID"
                  type="number"
                  min="1"
                  value={replaceId}
                  onChange={(e) => setReplaceId(e.target.value)}
                />
              </label>
            )}
          </div>
          <label className="block text-sm">
            Remarks
            <textarea
              aria-label="Document remarks"
              className="mt-2 w-full rounded border p-2"
              maxLength={2000}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
            />
          </label>
          {uploadMutation.isPending && (
            <div role="status">
              <progress
                aria-label="Upload progress"
                value={progress}
                max={100}
              />
              <span className="text-xs"> {progress}% uploaded</span>
            </div>
          )}
          {uploadError && (
            <p role="alert" className="text-sm text-destructive">
              {uploadError}
            </p>
          )}
          <Button
            aria-busy={(phone && uploadMutation.isPending) || undefined}
            data-save-action
            type="submit"
            disabled={
              !canUpload || uploadMutation.isPending || !effectiveEmployeeId
            }
          >
            <Upload className="h-4 w-4" />
            {uploadMutation.isPending ? "Uploading..." : "Upload document"}
          </Button>
        </CompactForm>
      </CardContent>
    </Card>
  );

  if (mode === "upload" && !canChooseEmployee && !effectiveEmployeeId)
    return (
      <p role="alert">
        Link an employee profile to your login before uploading documents.
      </p>
    );
  return mode === "upload" ? (
    uploadEditor
  ) : (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Spreadsheet metadata import</h2>
      <p className="text-sm text-muted-foreground">
        Map CSV / Excel columns to existing document record IDs, validate and
        update metadata. Upload binary files separately in Upload Documents.
      </p>
      <ImportWizard
        title="Prepare certificate import"
        label="Import spreadsheet"
        fields={[
          {
            key: "certificate_id",
            label: "Existing document record ID",
            type: "number",
            required: true,
          },
          ...certificateImportFields,
          { key: "category" },
          { key: "certificate_type" },
          { key: "issuing_entity" },
        ]}
        onImport={async ({ file }) => {
          const form = new FormData();
          if (effectiveEmployeeId)
            form.append("employee_id", effectiveEmployeeId);
          form.append(
            "remarks",
            "Mapped certificate import from Documents page",
          );
          form.append("process_metadata", "true");
          form.append("file", file);
          const result = await documentsApi.importCertificates(form);
          const d = result.data;
          return {
            message: `${d.success_count} document metadata records updated; ${d.failure_count} errors. Open import history for validation details. Binary files are unchanged.`,
          };
        }}
      />
    </div>
  );
}
