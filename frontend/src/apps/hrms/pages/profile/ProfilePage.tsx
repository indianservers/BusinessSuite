import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Banknote,
  Camera,
  CheckCircle2,
  FileText,
  FileUp,
  Fingerprint,
  Send,
  ShieldCheck,
  XCircle,
  MonitorSmartphone,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi, employeeApi } from "@/services/api";
import { assetUrl, formatDate, formatDateTime } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { useAuthStore } from "@/store/authStore";
import { usePageTitle } from "@/hooks/use-page-title";
import { getRoleKey } from "@/lib/roles";

const CHANGE_FIELDS = [
  "phone_number",
  "personal_email",
  "present_address",
  "permanent_address",
  "emergency_contact_name",
  "emergency_contact_number",
  "emergency_contact_relation",
  "marital_status",
  "bank_name",
  "bank_branch",
  "account_number",
  "ifsc_code",
  "pan_number",
  "aadhaar_number",
  "family_information",
] as const;

const DOCUMENT_TYPES = [
  "Aadhaar",
  "PAN",
  "Offer Letter",
  "Certificate",
  "Bank Proof",
  "Address Proof",
  "Previous Company Certificate",
  "Other",
];

type ChangeDraft = Record<(typeof CHANGE_FIELDS)[number], string>;

const emptyChangeDraft: ChangeDraft = {
  phone_number: "",
  personal_email: "",
  present_address: "",
  permanent_address: "",
  emergency_contact_name: "",
  emergency_contact_number: "",
  emergency_contact_relation: "",
  marital_status: "",
  bank_name: "",
  bank_branch: "",
  account_number: "",
  ifsc_code: "",
  pan_number: "",
  aadhaar_number: "",
  family_information: "",
};

export default function ProfilePage() {
  usePageTitle("Profile");
  const qc = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const canReviewChanges = ["admin", "hr", "manager"].includes(roleKey);
  const hasEmployeeProfile = Boolean(user?.employee_id);
  const [changeDraft, setChangeDraft] = useState<ChangeDraft>(emptyChangeDraft);
  const [changeReason, setChangeReason] = useState("Employee self-service profile update");
  const [documentDraft, setDocumentDraft] = useState({
    document_type: "Aadhaar",
    document_name: "",
    document_number: "",
    expiry_date: "",
  });
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [reviewRemarks, setReviewRemarks] = useState<Record<number, string>>({});
  const [mfaDialog, setMfaDialog] = useState<"setup" | "disable" | "regenerate" | null>(null);
  const [mfaStep, setMfaStep] = useState(1);
  const [mfaCode, setMfaCode] = useState("");
  const [savedRecoveryCodes, setSavedRecoveryCodes] = useState(false);
  const me = useQuery({ queryKey: ["me"], queryFn: () => authApi.me().then((r) => r.data) });
  const employee = useQuery({
    queryKey: ["my-employee-profile"],
    queryFn: () => employeeApi.me().then((r) => r.data),
    retry: false,
    enabled: hasEmployeeProfile,
  });
  const completeness = useQuery({
    queryKey: ["profile-completeness"],
    queryFn: () => employeeApi.profileCompleteness().then((r) => r.data),
    retry: false,
    enabled: hasEmployeeProfile,
  });
  const mfaStatus = useQuery({ queryKey: ["mfa-status"], queryFn: () => authApi.mfaStatus().then((r) => r.data) });
  const loginAttempts = useQuery({ queryKey: ["my-login-attempts"], queryFn: () => authApi.loginAttempts().then((r) => r.data) });
  const sessions = useQuery({
    queryKey: ["my-sessions", user?.id, user?.is_superuser],
    queryFn: () =>
      user?.is_superuser
        ? authApi.sessions({ user_id: user.id }).then((r) => r.data)
        : authApi.mySessions().then((r) => r.data),
    enabled: Boolean(user?.id),
    retry: false,
  });
  const employeeId = employee.data?.id || me.data?.employee_id;

  const fieldLabels = useMemo(() => ({
    phone_number: "Phone",
    personal_email: "Personal email",
    present_address: "Present address",
    permanent_address: "Permanent address",
    emergency_contact_name: "Emergency contact",
    emergency_contact_number: "Emergency phone",
    bank_name: "Bank name",
    bank_branch: "Bank branch",
    account_number: "Account number",
    ifsc_code: "IFSC",
    pan_number: "PAN",
    aadhaar_number: "Aadhaar",
    marital_status: "Marital status",
    emergency_contact_relation: "Emergency relation",
    family_information: "Nominee / family details",
    profile_photo_url: "Profile photo",
    date_of_birth: "Date of birth",
  } as Record<string, string>), []);

  const proposedChanges = useMemo(() => {
    const changes: Record<string, string> = {};
    CHANGE_FIELDS.forEach((field) => {
      const requested = changeDraft[field].trim();
      const current = String(employee.data?.[field] || "").trim();
      if (requested && requested !== current) changes[field] = requested;
    });
    return changes;
  }, [changeDraft, employee.data]);

  const completionNudges = useMemo(() => {
    const missing = new Set<string>(completeness.data?.missing || []);
    const hasDocs = Boolean(employee.data?.documents?.length);
    return [
      {
        title: "Bank details",
        description: "Needed for payroll, reimbursements, and full-and-final settlement.",
        icon: Banknote,
        active: ["bank_name", "account_number", "ifsc_code"].some((key) => missing.has(key)),
      },
      {
        title: "Identity details",
        description: "PAN and Aadhaar help statutory compliance and document verification.",
        icon: Fingerprint,
        active: ["pan_number", "aadhaar_number"].some((key) => missing.has(key)),
      },
      {
        title: "Documents",
        description: "Upload Aadhaar, PAN, offer letter, certificates, and prior company documents.",
        icon: FileText,
        active: !hasDocs,
      },
      {
        title: "Contact profile",
        description: "Keep phone, personal email, address, and emergency contact updated.",
        icon: ShieldCheck,
        active: ["phone_number", "personal_email", "present_address", "permanent_address", "emergency_contact_name"].some((key) => missing.has(key)),
      },
    ].filter((item) => item.active);
  }, [completeness.data?.missing, employee.data?.documents?.length]);

  const myChangeRequests = useQuery({
    queryKey: ["my-change-requests", employeeId],
    queryFn: () => employeeApi.changeRequests({ employee_id: employeeId }).then((r) => r.data),
    enabled: Boolean(employeeId),
    retry: false,
  });

  const pendingReviews = useQuery({
    queryKey: ["pending-profile-change-reviews"],
    queryFn: () => employeeApi.changeRequests({ status: "Pending" }).then((r) => r.data),
    enabled: canReviewChanges,
    retry: false,
  });

  const uploadPhoto = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return employeeApi.uploadPhoto(employeeId, form);
    },
    onSuccess: () => {
      toast({ title: "Photo uploaded" });
      qc.invalidateQueries({ queryKey: ["my-employee-profile"] });
      qc.invalidateQueries({ queryKey: ["profile-completeness"] });
    },
  });

  const changeRequest = useMutation({
    mutationFn: () => employeeApi.createProfileChangeRequest(employeeId, {
      requestType: "Profile Update",
      effectiveDate: new Date().toISOString().slice(0, 10),
      fieldChanges: proposedChanges,
      reason: changeReason || "Employee self-service profile update",
    }),
    onSuccess: () => {
      toast({ title: "Change request submitted" });
      setChangeDraft(emptyChangeDraft);
      setChangeReason("Employee self-service profile update");
      qc.invalidateQueries({ queryKey: ["profile-completeness"] });
      qc.invalidateQueries({ queryKey: ["my-change-requests", employeeId] });
      qc.invalidateQueries({ queryKey: ["pending-profile-change-reviews"] });
    },
  });

  const uploadDocument = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("document_type", documentDraft.document_type);
      form.append("document_name", documentDraft.document_name || `${documentDraft.document_type} document`);
      if (documentDraft.document_number) form.append("document_number", documentDraft.document_number);
      if (documentDraft.expiry_date) form.append("expiry_date", documentDraft.expiry_date);
      if (documentFile) form.append("file", documentFile);
      return employeeApi.uploadDocument(employeeId, form);
    },
    onSuccess: () => {
      toast({ title: "Document uploaded", description: "HR can now verify it from employee documents." });
      setDocumentDraft({ document_type: "Aadhaar", document_name: "", document_number: "", expiry_date: "" });
      setDocumentFile(null);
      qc.invalidateQueries({ queryKey: ["my-employee-profile"] });
      qc.invalidateQueries({ queryKey: ["profile-completeness"] });
    },
  });

  const reviewChange = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "Approved" | "Rejected" }) =>
      status === "Approved"
        ? employeeApi.approveProfileChangeRequest(id, {
            applyChanges: true,
            remarks: reviewRemarks[id] || undefined,
          })
        : employeeApi.rejectProfileChangeRequest(id, {
            remarks: reviewRemarks[id] || undefined,
          }),
    onSuccess: () => {
      toast({ title: "Change request reviewed" });
      qc.invalidateQueries({ queryKey: ["pending-profile-change-reviews"] });
      qc.invalidateQueries({ queryKey: ["my-change-requests", employeeId] });
      qc.invalidateQueries({ queryKey: ["my-employee-profile"] });
      qc.invalidateQueries({ queryKey: ["profile-completeness"] });
    },
  });
  const mfaSetup = useMutation({
    mutationFn: () => authApi.mfaSetup(),
    onSuccess: () => setMfaStep(1),
    onError: () => toast({ title: "Unable to start MFA setup", variant: "destructive" }),
  });
  const confirmMfa = useMutation({
    mutationFn: () => authApi.mfaConfirm({ method_id: mfaSetup.data?.data.method_id, code: mfaCode }),
    onSuccess: () => {
      toast({ title: "2FA enabled" });
      setMfaStep(3);
      qc.invalidateQueries({ queryKey: ["mfa-status"] });
    },
    onError: () => toast({ title: "Incorrect code. Please try again.", variant: "destructive" }),
  });
  const disableMfa = useMutation({
    mutationFn: () => authApi.mfaDisable({ code: mfaCode }),
    onSuccess: () => {
      toast({ title: "2FA disabled" });
      setMfaDialog(null);
      setMfaCode("");
      qc.invalidateQueries({ queryKey: ["mfa-status"] });
    },
  });
  const regenerateCodes = useMutation({
    mutationFn: () => authApi.regenerateRecoveryCodes({ code: mfaCode }),
    onSuccess: () => {
      toast({ title: "Recovery codes regenerated" });
      setMfaStep(3);
      qc.invalidateQueries({ queryKey: ["mfa-status"] });
    },
  });
  const revokeSession = useMutation({
    mutationFn: (id: number) => authApi.revokeMySession(id),
    onSuccess: () => {
      toast({ title: "Session revoked" });
      qc.invalidateQueries({ queryKey: ["my-sessions"] });
    },
  });
  const revokeOthers = useMutation({
    mutationFn: () => authApi.revokeOtherSessions(),
    onSuccess: (response) => {
      toast({ title: "Other sessions revoked", description: `${response.data.revoked || 0} session(s) ended.` });
      qc.invalidateQueries({ queryKey: ["my-sessions"] });
    },
  });

  function openMfaSetup() {
    setMfaDialog("setup");
    setMfaStep(1);
    setMfaCode("");
    setSavedRecoveryCodes(false);
    mfaSetup.mutate();
  }

  function updateChange(field: keyof ChangeDraft, value: string) {
    setChangeDraft((current) => ({ ...current, [field]: value }));
  }

  function onPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file && employeeId) uploadPhoto.mutate(file);
  }

  function onDocumentFile(event: ChangeEvent<HTMLInputElement>) {
    setDocumentFile(event.target.files?.[0] || null);
  }

  function submitChange(event: FormEvent) {
    event.preventDefault();
    if (!employeeId) return;
    if (!Object.keys(proposedChanges).length) {
      toast({ title: "Add at least one real change", variant: "destructive" });
      return;
    }
    changeRequest.mutate();
  }

  function submitDocument(event: FormEvent) {
    event.preventDefault();
    if (!employeeId || !documentFile) {
      toast({ title: "Choose a document file", variant: "destructive" });
      return;
    }
    uploadDocument.mutate();
  }

  const documents = employee.data?.documents || [];
  const missing = completeness.data?.missing || [];

  return (
    <div className="space-y-5">
      <div className="rounded-lg border bg-card p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">ESS Portal</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">My Profile</h1>
        <p className="mt-1 text-sm text-muted-foreground">Profile completion, verified documents, and approved master-data changes.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Profile Completion</CardTitle>
            <CardDescription>Nudges employees to complete payroll, statutory, and document data</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="relative h-20 w-20 overflow-hidden rounded-full border bg-muted">
                {employee.data?.profile_photo_url ? (
                  <img src={assetUrl(employee.data.profile_photo_url)} alt="Profile" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xl font-semibold text-muted-foreground">
                    {employee.data?.first_name?.[0] || "U"}
                  </div>
                )}
              </div>
              <div>
                <Label htmlFor="profile-photo" className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted">
                  <Camera className="h-4 w-4" />
                  Upload photo
                </Label>
                <input id="profile-photo" type="file" accept="image/png,image/jpeg" className="hidden" onChange={onPhoto} />
                <p className="mt-2 text-xs text-muted-foreground">Employees can upload their own photo; HR can still manage records.</p>
              </div>
            </div>
            <div>
              <div className="mb-2 flex justify-between text-sm">
                <span>Completion</span>
                <span className="font-semibold">{completeness.data?.percent ?? 0}%</span>
              </div>
              <div className="h-2 rounded-full bg-muted">
                <div className="h-2 rounded-full bg-primary" style={{ width: `${completeness.data?.percent ?? 0}%` }} />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {missing.slice(0, 10).map((key: string) => (
                <Badge key={key} variant="outline">{fieldLabels[key] || key}</Badge>
              ))}
              {missing.length === 0 && (
                <span className="flex items-center gap-2 text-sm text-emerald-600"><CheckCircle2 className="h-4 w-4" /> Complete</span>
              )}
            </div>
            <div className="space-y-2">
              {completionNudges.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.title} className="flex gap-3 rounded-md border p-3">
                    <Icon className="mt-0.5 h-4 w-4 text-primary" />
                    <div>
                      <p className="text-sm font-medium">{item.title}</p>
                      <p className="text-xs text-muted-foreground">{item.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              Pending change requests: {completeness.data?.pending_change_requests ?? 0}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Employee Details</CardTitle><CardDescription>Current approved employee master data</CardDescription></CardHeader>
          <CardContent>
            {employee.data ? (
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <div><p className="text-muted-foreground">Name</p><p className="font-medium">{employee.data.first_name} {employee.data.last_name}</p></div>
                <div><p className="text-muted-foreground">Employee ID</p><p className="font-medium">{employee.data.employee_id}</p></div>
                <div><p className="text-muted-foreground">Email</p><p className="font-medium">{employee.data.personal_email || "-"}</p></div>
                <div><p className="text-muted-foreground">Phone</p><p className="font-medium">{employee.data.phone_number || "-"}</p></div>
                <div><p className="text-muted-foreground">Marital status</p><p className="font-medium">{employee.data.marital_status || "-"}</p></div>
                <div><p className="text-muted-foreground">Emergency contact</p><p className="font-medium">{employee.data.emergency_contact_name || "-"}</p></div>
                <div><p className="text-muted-foreground">Emergency phone</p><p className="font-medium">{employee.data.emergency_contact_number || "-"}</p></div>
                <div><p className="text-muted-foreground">PAN</p><p className="font-medium">{employee.data.pan_number || "-"}</p></div>
                <div><p className="text-muted-foreground">Aadhaar</p><p className="font-medium">{employee.data.aadhaar_number || "-"}</p></div>
                <div><p className="text-muted-foreground">Bank</p><p className="font-medium">{employee.data.bank_name || "-"}</p></div>
                <div><p className="text-muted-foreground">IFSC</p><p className="font-medium">{employee.data.ifsc_code || "-"}</p></div>
                <div><p className="text-muted-foreground">Joining date</p><p className="font-medium">{formatDate(employee.data.date_of_joining)}</p></div>
                <div><p className="text-muted-foreground">Status</p><Badge variant="secondary">{employee.data.status}</Badge></div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{employeeId ? "Loading employee details..." : "No employee profile is linked to this login."}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Request Profile Change</CardTitle>
          <CardDescription>Employees submit sensitive changes; HR or the reporting manager approves with a diff view.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <form onSubmit={submitChange} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1.5"><Label>Phone</Label><Input value={changeDraft.phone_number} onChange={(e) => updateChange("phone_number", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Personal email</Label><Input type="email" value={changeDraft.personal_email} onChange={(e) => updateChange("personal_email", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Marital status</Label><Input value={changeDraft.marital_status} onChange={(e) => updateChange("marital_status", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Emergency contact</Label><Input value={changeDraft.emergency_contact_name} onChange={(e) => updateChange("emergency_contact_name", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Emergency phone</Label><Input value={changeDraft.emergency_contact_number} onChange={(e) => updateChange("emergency_contact_number", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Emergency relation</Label><Input value={changeDraft.emergency_contact_relation} onChange={(e) => updateChange("emergency_contact_relation", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>PAN</Label><Input value={changeDraft.pan_number} onChange={(e) => updateChange("pan_number", e.target.value.toUpperCase())} /></div>
              <div className="space-y-1.5"><Label>Aadhaar</Label><Input value={changeDraft.aadhaar_number} onChange={(e) => updateChange("aadhaar_number", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Bank name</Label><Input value={changeDraft.bank_name} onChange={(e) => updateChange("bank_name", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Bank branch</Label><Input value={changeDraft.bank_branch} onChange={(e) => updateChange("bank_branch", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>Account number</Label><Input value={changeDraft.account_number} onChange={(e) => updateChange("account_number", e.target.value)} /></div>
              <div className="space-y-1.5"><Label>IFSC</Label><Input value={changeDraft.ifsc_code} onChange={(e) => updateChange("ifsc_code", e.target.value.toUpperCase())} /></div>
              <div className="space-y-1.5 md:col-span-2 lg:col-span-1"><Label>Reason</Label><Input value={changeReason} onChange={(e) => setChangeReason(e.target.value)} /></div>
              <div className="space-y-1.5 md:col-span-2 lg:col-span-3"><Label>Present address</Label><Input value={changeDraft.present_address} onChange={(e) => updateChange("present_address", e.target.value)} /></div>
              <div className="space-y-1.5 md:col-span-2 lg:col-span-3"><Label>Permanent address</Label><Input value={changeDraft.permanent_address} onChange={(e) => updateChange("permanent_address", e.target.value)} /></div>
              <div className="space-y-1.5 md:col-span-2 lg:col-span-3">
                <Label>Nominee / family details</Label>
                <textarea value={changeDraft.family_information} onChange={(e) => updateChange("family_information", e.target.value)} rows={3} className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="rounded-md border">
              <div className="grid grid-cols-[0.8fr_1fr_1fr] gap-3 border-b bg-muted/50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <span>Field</span><span>Current</span><span>Requested</span>
              </div>
              {Object.keys(proposedChanges).length ? (
                Object.entries(proposedChanges).map(([field, value]) => (
                  <div key={field} className="grid grid-cols-[0.8fr_1fr_1fr] gap-3 border-b px-3 py-2 text-sm last:border-b-0">
                    <span className="font-medium">{fieldLabels[field] || field}</span>
                    <span className="break-words text-muted-foreground">{employee.data?.[field] || "-"}</span>
                    <span className="break-words">{value}</span>
                  </div>
                ))
              ) : (
                <p className="px-3 py-4 text-sm text-muted-foreground">Enter a new value to preview the approval diff.</p>
              )}
            </div>
            <Button type="submit" disabled={changeRequest.isPending || !employeeId || !Object.keys(proposedChanges).length}>
              <Send className="mr-2 h-4 w-4" />
              Submit change request
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Profile Documents</CardTitle>
            <CardDescription>Aadhaar, PAN, offer letter, study certificates, and old company certificates</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={submitDocument} className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Document type</Label>
                <select
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                  value={documentDraft.document_type}
                  onChange={(e) => setDocumentDraft((current) => ({ ...current, document_type: e.target.value }))}
                >
                  {DOCUMENT_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                </select>
              </div>
              <div className="space-y-1.5"><Label>Document name</Label><Input value={documentDraft.document_name} onChange={(e) => setDocumentDraft((current) => ({ ...current, document_name: e.target.value }))} placeholder="Class X marksheet, PAN card..." /></div>
              <div className="space-y-1.5"><Label>Document number</Label><Input value={documentDraft.document_number} onChange={(e) => setDocumentDraft((current) => ({ ...current, document_number: e.target.value }))} /></div>
              <div className="space-y-1.5"><Label>Expiry date</Label><Input type="date" value={documentDraft.expiry_date} onChange={(e) => setDocumentDraft((current) => ({ ...current, expiry_date: e.target.value }))} /></div>
              <div className="space-y-1.5 md:col-span-2">
                <Label>PDF or image</Label>
                <Input type="file" accept=".pdf,image/png,image/jpeg" onChange={onDocumentFile} />
              </div>
              <Button type="submit" disabled={uploadDocument.isPending || !documentFile || !employeeId} className="md:col-span-2">
                <FileUp className="mr-2 h-4 w-4" />
                Upload document
              </Button>
            </form>
            <div className="space-y-2">
              {documents.map((doc: any) => (
                <div key={doc.id} className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
                  <div>
                    <p className="font-medium">{doc.document_name || doc.document_type}</p>
                    <p className="text-xs text-muted-foreground">{doc.document_type} {doc.document_number ? `- ${doc.document_number}` : ""}</p>
                    <p className="text-xs text-muted-foreground">Expiry: {formatDate(doc.expiry_date)} | Verified: {doc.verification_status || (doc.is_verified ? "Verified" : "Pending")}</p>
                  </div>
                  {doc.file_url && (
                    <Button variant="outline" size="sm" asChild>
                      <a href={assetUrl(doc.file_url)} target="_blank" rel="noreferrer">View</a>
                    </Button>
                  )}
                </div>
              ))}
              {!documents.length && <p className="rounded-md border p-4 text-sm text-muted-foreground">No profile documents uploaded yet.</p>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">My Change Requests</CardTitle>
            <CardDescription>Status trail for submitted employee profile changes</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {(myChangeRequests.data || []).map((request: any) => (
              <div key={request.id} className="rounded-md border p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{request.request_type}</p>
                  <Badge variant={request.status === "Rejected" ? "destructive" : "secondary"}>{request.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(request.created_at)} | {request.reason || "No reason provided"}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.keys(request.field_changes_json || {}).map((field) => (
                    <Badge key={field} variant="outline">{fieldLabels[field] || field}</Badge>
                  ))}
                </div>
                {request.review_remarks && <p className="mt-2 text-xs text-muted-foreground">Reviewer note: {request.review_remarks}</p>}
              </div>
            ))}
            {!myChangeRequests.data?.length && <p className="rounded-md border p-4 text-sm text-muted-foreground">No change requests yet.</p>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-5 w-5 text-primary" />
              Two-Factor Authentication
            </CardTitle>
            <CardDescription>Add an extra layer of security to your account</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {mfaStatus.isLoading ? <div className="h-24 animate-pulse rounded bg-muted" /> : mfaStatus.data?.mfa_enabled ? (
              <>
                <Badge className="bg-green-100 text-green-800"><CheckCircle2 className="mr-1 h-3 w-3" />2FA Enabled</Badge>
                <p className="text-sm text-muted-foreground">Enabled {mfaStatus.data.verified_at ? formatDate(mfaStatus.data.verified_at) : "recently"}</p>
                <p className="text-sm">Recovery codes remaining: {mfaStatus.data.recovery_codes_remaining}</p>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => { setMfaDialog("regenerate"); setMfaCode(""); setMfaStep(2); }}>Regenerate Recovery Codes</Button>
                  <Button variant="destructive" onClick={() => { setMfaDialog("disable"); setMfaCode(""); }}>Disable 2FA</Button>
                </div>
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">Authenticator app verification is currently off.</p>
                <Button onClick={openMfaSetup}>Enable 2FA</Button>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Security Events</CardTitle>
            <CardDescription>Recent login attempts for your account</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">Date/Time</th><th className="px-3 py-2 text-left">IP Address</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-left">MFA</th></tr></thead>
                <tbody>
                  {(loginAttempts.data || []).slice(0, 10).map((attempt: any) => (
                    <tr key={attempt.id} className="border-t">
                      <td className="px-3 py-2">{formatDateTime(attempt.created_at)}</td>
                      <td className="px-3 py-2">{attempt.ip_address || "-"}</td>
                      <td className="px-3 py-2"><Badge variant={attempt.success === false || attempt.status === "Failed" ? "destructive" : "secondary"}>{attempt.status}</Badge></td>
                      <td className="px-3 py-2">{attempt.mfa_attempted ? <Badge variant="outline">{attempt.mfa_success ? "Passed" : "Failed"}</Badge> : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base"><MonitorSmartphone className="h-5 w-5 text-primary" />Active Sessions & Devices</CardTitle>
              <CardDescription>Review trusted devices and revoke sessions you no longer recognize.</CardDescription>
            </div>
            <Button variant="outline" onClick={() => revokeOthers.mutate()} disabled={revokeOthers.isPending}>Revoke other sessions</Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-muted/60"><tr><th className="px-3 py-2 text-left">Device</th><th className="px-3 py-2 text-left">IP</th><th className="px-3 py-2 text-left">Trusted</th><th className="px-3 py-2 text-left">Last Seen</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-right">Actions</th></tr></thead>
              <tbody>
                {(sessions.data || []).map((session: any) => (
                  <tr key={session.id} className="border-t">
                    <td className="px-3 py-2">{session.device_name || "Unknown device"}</td>
                    <td className="px-3 py-2">{session.ip_address || "-"}</td>
                    <td className="px-3 py-2">{session.trusted_device ? <Badge variant="outline">Trusted</Badge> : "-"}</td>
                    <td className="px-3 py-2">{formatDateTime(session.last_seen_at || session.created_at)}</td>
                    <td className="px-3 py-2"><Badge variant={String(session.status).toLowerCase() === "revoked" ? "destructive" : "secondary"}>{session.status}</Badge></td>
                    <td className="px-3 py-2 text-right"><Button size="sm" variant="ghost" disabled={String(session.status).toLowerCase() === "revoked" || revokeSession.isPending} onClick={() => revokeSession.mutate(session.id)}>Revoke</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {canReviewChanges && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">HR / Manager Approval Queue</CardTitle>
            <CardDescription>Review employee submitted changes with current-vs-requested diff before applying.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(pendingReviews.data || []).filter((request: any) => request.employee_id !== employeeId).map((request: any) => (
              <div key={request.id} className="rounded-md border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{request.employee_name || `Employee #${request.employee_id}`}</p>
                    <p className="text-xs text-muted-foreground">{request.employee_code || "-"} | {request.reason || "No reason provided"}</p>
                  </div>
                  <Badge variant="outline">{request.request_type}</Badge>
                </div>
                <div className="mt-3 rounded-md border">
                  <div className="grid grid-cols-[0.8fr_1fr_1fr] gap-3 border-b bg-muted/50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    <span>Field</span><span>Current</span><span>Requested</span>
                  </div>
                  {Object.entries(request.field_changes_json || {}).map(([field, value]) => (
                    <div key={field} className="grid grid-cols-[0.8fr_1fr_1fr] gap-3 border-b px-3 py-2 text-sm last:border-b-0">
                      <span className="font-medium">{fieldLabels[field] || field}</span>
                      <span className="break-words text-muted-foreground">{request.current_values_json?.[field] || "-"}</span>
                      <span className="break-words">{String(value || "-")}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto_auto]">
                  <Input
                    placeholder="Approval or rejection reason"
                    value={reviewRemarks[request.id] || ""}
                    onChange={(e) => setReviewRemarks((current) => ({ ...current, [request.id]: e.target.value }))}
                  />
                  <Button variant="outline" disabled={reviewChange.isPending} onClick={() => reviewChange.mutate({ id: request.id, status: "Rejected" })}>
                    <XCircle className="mr-2 h-4 w-4" />
                    Reject
                  </Button>
                  <Button disabled={reviewChange.isPending} onClick={() => reviewChange.mutate({ id: request.id, status: "Approved" })}>
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    Approve
                  </Button>
                </div>
              </div>
            ))}
            {!pendingReviews.data?.filter((request: any) => request.employee_id !== employeeId).length && (
              <p className="rounded-md border p-4 text-sm text-muted-foreground">No pending profile changes for your approval queue.</p>
            )}
          </CardContent>
        </Card>
      )}
      {mfaDialog && (
        <MfaDialog
          mode={mfaDialog}
          step={mfaStep}
          setStep={setMfaStep}
          setupData={mfaSetup.data?.data}
          regenerateData={regenerateCodes.data?.data}
          code={mfaCode}
          setCode={setMfaCode}
          saved={savedRecoveryCodes}
          setSaved={setSavedRecoveryCodes}
          onClose={() => { setMfaDialog(null); qc.invalidateQueries({ queryKey: ["mfa-status"] }); }}
          onConfirm={() => confirmMfa.mutate()}
          onDisable={() => disableMfa.mutate()}
          onRegenerate={() => regenerateCodes.mutate()}
          pending={confirmMfa.isPending || disableMfa.isPending || regenerateCodes.isPending}
        />
      )}
    </div>
  );
}

function MfaDialog({
  mode, step, setStep, setupData, regenerateData, code, setCode, saved, setSaved, onClose, onConfirm, onDisable, onRegenerate, pending,
}: {
  mode: "setup" | "disable" | "regenerate";
  step: number;
  setStep: (step: number) => void;
  setupData?: { qr_base64: string; secret: string; recovery_codes: string[] };
  regenerateData?: { recovery_codes: string[] };
  code: string;
  setCode: (value: string) => void;
  saved: boolean;
  setSaved: (value: boolean) => void;
  onClose: () => void;
  onConfirm: () => void;
  onDisable: () => void;
  onRegenerate: () => void;
  pending: boolean;
}) {
  const codes = regenerateData?.recovery_codes || setupData?.recovery_codes || [];
  const copyCodes = () => navigator.clipboard.writeText(codes.join("\n"));
  const downloadCodes = () => {
    const url = URL.createObjectURL(new Blob([codes.join("\n")], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "ai-hrms-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-background p-5 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">{mode === "setup" ? "Set Up Authenticator App" : mode === "disable" ? "Disable 2FA" : "Regenerate Recovery Codes"}</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
        </div>
        {mode === "disable" ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Enter your current authenticator code. Disabling 2FA reduces account protection.</p>
            <Input value={code} maxLength={6} onChange={(e) => setCode(e.target.value)} placeholder="123456" />
            <Button variant="destructive" disabled={!code || pending} onClick={onDisable}>Disable 2FA</Button>
          </div>
        ) : step === 1 && mode === "setup" ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Scan this QR code with Google Authenticator, Authy, or any TOTP app.</p>
            {setupData?.qr_base64 ? <img src={`data:image/png;base64,${setupData.qr_base64}`} alt="MFA QR code" className="mx-auto h-48 w-48 rounded border bg-white p-2" /> : <div className="h-48 animate-pulse rounded bg-muted" />}
            <details className="rounded border p-3 text-sm"><summary>Can't scan?</summary><code className="mt-2 block break-all">{setupData?.secret}</code></details>
            <Button onClick={() => setStep(2)} disabled={!setupData}>Next</Button>
          </div>
        ) : step === 2 ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Enter the 6-digit code from your authenticator app.</p>
            <Input value={code} maxLength={6} onChange={(e) => setCode(e.target.value)} placeholder="123456" />
            <Button disabled={!code || pending} onClick={mode === "regenerate" ? onRegenerate : onConfirm}>{mode === "regenerate" ? "Regenerate" : "Verify"}</Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-900">Save these codes somewhere safe. They can only be shown once and cannot be recovered.</div>
            <div className="grid grid-cols-2 gap-2 rounded-md border p-3 font-mono text-sm">{codes.map((item) => <span key={item}>{item}</span>)}</div>
            <div className="flex gap-2"><Button variant="outline" onClick={copyCodes}>Copy All</Button><Button variant="outline" onClick={downloadCodes}>Download as TXT</Button></div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} />I have saved my recovery codes</label>
            <Button disabled={!saved} onClick={onClose}>Done</Button>
          </div>
        )}
      </div>
    </div>
  );
}
