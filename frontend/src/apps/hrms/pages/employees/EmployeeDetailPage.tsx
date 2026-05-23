import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import type React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Banknote, Briefcase, CalendarDays, Camera, ChevronLeft, Clock, CreditCard, FileText, GraduationCap, HeartPulse, HelpCircle, Link2, Package, Save, Star, Target, Unlink, User, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { employeeApi } from "@/services/api";
import { assetUrl, formatDate, getInitials, statusColor } from "@/lib/utils";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";

const TABS = [
  { id: "360", label: "360 Timeline", icon: Activity },
  { id: "personal", label: "Personal", icon: User },
  { id: "job", label: "Job", icon: Briefcase },
  { id: "education", label: "Education", icon: GraduationCap },
  { id: "experience", label: "Experience", icon: Briefcase },
  { id: "skills", label: "Skills", icon: Star },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "account", label: "Account", icon: Link2 },
  { id: "family", label: "Family", icon: Users },
  { id: "health", label: "Health", icon: HeartPulse },
  { id: "bank", label: "Bank & Tax", icon: CreditCard },
];

const EDIT_FIELDS: Record<string, Array<[string, string, string?]>> = {
  personal: [
    ["first_name", "First Name"],
    ["middle_name", "Middle Name"],
    ["last_name", "Last Name"],
    ["personal_email", "Email"],
    ["phone_number", "Phone"],
    ["alternate_phone", "Alternate Phone"],
    ["emergency_contact_name", "Emergency Contact"],
    ["emergency_contact_number", "Emergency Phone"],
    ["emergency_contact_relation", "Relation"],
    ["present_address", "Present Address", "textarea"],
    ["bio", "Bio", "textarea"],
    ["interests", "Interests", "textarea"],
    ["research_work", "Research / Publications", "textarea"],
  ],
  job: [
    ["employment_type", "Employment Type"],
    ["status", "Status"],
    ["work_location", "Work Location"],
    ["date_of_joining", "Date of Joining", "date"],
    ["date_of_confirmation", "Date of Confirmation", "date"],
  ],
  family: [["family_information", "Family Information", "textarea"]],
  health: [["health_information", "Health Information", "textarea"]],
  bank: [
    ["bank_name", "Bank Name"],
    ["bank_branch", "Bank Branch"],
    ["account_number", "Account Number"],
    ["ifsc_code", "IFSC"],
    ["pan_number", "PAN"],
    ["aadhaar_number", "Aadhaar"],
    ["uan_number", "UAN"],
    ["pf_number", "PF Number"],
    ["esic_number", "ESIC Number"],
  ],
};

function getApiErrorMessage(error: unknown): string {
  const responseData = (error as { response?: { data?: { detail?: unknown; message?: unknown } }; message?: string })?.response?.data;
  const detail = responseData?.detail || responseData?.message;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const location = Array.isArray(item?.loc) ? item.loc.filter((part: string) => part !== "body").join(".") : "";
        const message = item?.msg || item?.message || "Invalid value";
        return location ? `${location}: ${message}` : message;
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    return Object.entries(detail as Record<string, unknown>)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
      .join("; ");
  }
  return (error as { message?: string })?.message || "Please check the required fields and try again.";
}

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState("personal");
  const [editForm, setEditForm] = useState<Record<string, any>>({});
  const [educationForm, setEducationForm] = useState<Record<string, any>>({});
  const [experienceForm, setExperienceForm] = useState<Record<string, any>>({});
  const [skillForm, setSkillForm] = useState<Record<string, any>>({});
  const [selectedUserId, setSelectedUserId] = useState("");
  const editing = params.get("edit") === "true";
  usePageTitle("Employee Details");

  const { data: emp, isLoading, error: employeeError } = useQuery({
    queryKey: ["employee", id],
    queryFn: () => employeeApi.get(Number(id)).then((r) => r.data),
    enabled: !!id,
  });

  const userOptions = useQuery({
    queryKey: ["employee-user-options", id],
    queryFn: () =>
      employeeApi
        .userOptions({ include_employee_id: Number(id) })
        .then((r) => r.data as Array<{ id: number; email: string; role?: string | null; employee_id?: number | null; employee_code?: string | null; employee_name?: string | null }>),
    enabled: !!id,
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, any>) => employeeApi.update(Number(id), payload),
    onSuccess: () => {
      toast({ title: "Employee updated" });
      qc.invalidateQueries({ queryKey: ["employee", id] });
      setParams({});
    },
    onError: () => toast({ title: "Could not update employee", variant: "destructive" }),
  });

  const photoMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return employeeApi.uploadPhoto(Number(id), form);
    },
    onSuccess: () => {
      toast({ title: "Photo updated" });
      qc.invalidateQueries({ queryKey: ["employee", id] });
    },
    onError: () => toast({ title: "Could not upload photo", variant: "destructive" }),
  });

  const educationMutation = useMutation({
    mutationFn: (payload: Record<string, any>) => employeeApi.addEducation(Number(id), payload),
    onSuccess: () => {
      toast({ title: "Education added" });
      setEducationForm({});
      qc.invalidateQueries({ queryKey: ["employee", id] });
    },
    onError: (err: unknown) => toast({
      title: "Could not add education",
      description: getApiErrorMessage(err),
      variant: "destructive",
    }),
  });

  const experienceMutation = useMutation({
    mutationFn: (payload: Record<string, any>) => employeeApi.addExperience(Number(id), payload),
    onSuccess: () => {
      toast({ title: "Experience added" });
      setExperienceForm({});
      qc.invalidateQueries({ queryKey: ["employee", id] });
    },
    onError: (err: unknown) => toast({
      title: "Could not add experience",
      description: getApiErrorMessage(err),
      variant: "destructive",
    }),
  });

  const skillMutation = useMutation({
    mutationFn: (payload: Record<string, any>) => employeeApi.addSkill(Number(id), payload),
    onSuccess: () => {
      toast({ title: "Skill added" });
      setSkillForm({});
      qc.invalidateQueries({ queryKey: ["employee", id] });
    },
    onError: (err: unknown) => toast({
      title: "Could not add skill",
      description: getApiErrorMessage(err),
      variant: "destructive",
    }),
  });

  const linkUserMutation = useMutation({
    mutationFn: (userId: number | null) => employeeApi.linkUser(Number(id), userId),
    onSuccess: () => {
      toast({ title: "User mapping updated" });
      qc.invalidateQueries({ queryKey: ["employee", id] });
      qc.invalidateQueries({ queryKey: ["employee-user-options", id] });
    },
    onError: (err: unknown) => toast({
      title: "Could not update user mapping",
      description: getApiErrorMessage(err),
      variant: "destructive",
    }),
  });

  useEffect(() => {
    if (!emp || !editing) return;
    setEditForm({
      first_name: emp.first_name || "",
      middle_name: emp.middle_name || "",
      last_name: emp.last_name || "",
      personal_email: emp.personal_email || "",
      phone_number: emp.phone_number || "",
      alternate_phone: emp.alternate_phone || "",
      employment_type: emp.employment_type || "Full-time",
      status: emp.status || "Active",
      work_location: emp.work_location || "Office",
      date_of_joining: emp.date_of_joining || "",
      date_of_confirmation: emp.date_of_confirmation || "",
      emergency_contact_name: emp.emergency_contact_name || "",
      emergency_contact_number: emp.emergency_contact_number || "",
      emergency_contact_relation: emp.emergency_contact_relation || "",
      present_address: emp.present_address || "",
      present_city: emp.present_city || "",
      present_state: emp.present_state || "",
      present_pincode: emp.present_pincode || "",
      bank_name: emp.bank_name || "",
      bank_branch: emp.bank_branch || "",
      account_number: emp.account_number || "",
      ifsc_code: emp.ifsc_code || "",
      pan_number: emp.pan_number || "",
      aadhaar_number: emp.aadhaar_number || "",
      uan_number: emp.uan_number || "",
      pf_number: emp.pf_number || "",
      esic_number: emp.esic_number || "",
      bio: emp.bio || "",
      interests: emp.interests || "",
      research_work: emp.research_work || "",
      family_information: emp.family_information || "",
      health_information: emp.health_information || "",
    });
  }, [emp, editing]);

  useEffect(() => {
    if (!emp) return;
    setSelectedUserId(emp.user_id ? String(emp.user_id) : "");
  }, [emp]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 skeleton rounded" />
        <div className="h-32 w-full skeleton rounded-xl" />
        <div className="h-64 w-full skeleton rounded-xl" />
      </div>
    );
  }

  if (employeeError) {
    return (
      <Card>
        <CardContent className="flex flex-col items-start gap-3 p-6">
          <Button variant="ghost" size="sm" onClick={() => navigate("/hrms/employees")}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Employees
          </Button>
          <div>
            <h2 className="text-xl font-semibold">Employee profile could not be loaded</h2>
            <p className="mt-1 text-sm text-muted-foreground">{getApiErrorMessage(employeeError)}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!emp) {
    return (
      <Card>
        <CardContent className="flex flex-col items-start gap-3 p-6">
          <Button variant="ghost" size="sm" onClick={() => navigate("/hrms/employees")}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Employees
          </Button>
          <div>
            <h2 className="text-xl font-semibold">Employee not found</h2>
            <p className="mt-1 text-sm text-muted-foreground">This profile may have been removed or you may not have access.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const initials = getInitials(`${emp.first_name} ${emp.last_name}`);
  const linkedUser = (userOptions.data || []).find((user) => user.id === emp.user_id);
  const employee360Events = buildEmployee360Events(emp);
  const skillCount = emp.skills?.length || 0;
  const documentCount = emp.documents?.length || 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/hrms/employees")}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Employees
        </Button>
      </div>

      {/* Profile header */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
            {emp.profile_photo_url ? (
              <img
                src={assetUrl(emp.profile_photo_url)}
                alt={initials}
                className="h-20 w-20 rounded-full object-cover border-4 border-background shadow-lg"
              />
            ) : (
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10 text-primary text-2xl font-bold border-4 border-background shadow-lg">
                {initials}
              </div>
            )}
            <label className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs hover:bg-muted">
              <Camera className="h-3.5 w-3.5" />
              Photo
              <input
                type="file"
                accept="image/png,image/jpeg"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) photoMutation.mutate(file);
                  event.currentTarget.value = "";
                }}
              />
            </label>
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="text-2xl font-bold">
                  {emp.first_name} {emp.last_name}
                </h2>
                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColor(emp.status)}`}>
                  {emp.status}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{emp.employee_id}</p>
              <div className="flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
                {emp.personal_email && <span>✉ {emp.personal_email}</span>}
                {emp.phone_number && <span>📞 {emp.phone_number}</span>}
                <span>Joined {formatDate(emp.date_of_joining)}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <AskAiButton
                module="HRMS"
                relatedEntityType="employee"
                relatedEntityId={id}
                defaultAgentCode="hrms_letter_drafting"
                defaultPrompt="Help me prepare HR action or summary for this employee."
              />
              <Button variant="outline" size="sm" onClick={() => setParams(editing ? {} : { edit: "true" })}>
                {editing ? "Cancel Edit" : "Edit"}
              </Button>
              <Badge variant="outline">{emp.employment_type}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <div className="flex overflow-x-auto gap-1 border-b pb-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {editing && (
        <Card>
          <CardHeader><CardTitle>Edit {TABS.find((tab) => tab.id === activeTab)?.label || "Employee"}</CardTitle></CardHeader>
          <CardContent>
            {EDIT_FIELDS[activeTab] && (
              <form
                className="grid gap-4 sm:grid-cols-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  const allowedFields = EDIT_FIELDS[activeTab].map(([key]) => key);
                  const payload = allowedFields.reduce<Record<string, any>>((acc, key) => {
                    acc[key] = editForm[key] === "" ? null : editForm[key];
                    return acc;
                  }, {});
                  updateMutation.mutate(payload);
                }}
              >
                {EDIT_FIELDS[activeTab].map(([key, label, type]) => (
                  <div key={key} className={`space-y-2 ${type === "textarea" ? "sm:col-span-2" : ""}`}>
                    <Label>{label}</Label>
                    {type === "textarea" ? (
                      <textarea
                        value={editForm[key] ?? ""}
                        onChange={(e) => setEditForm((f) => ({ ...f, [key]: e.target.value }))}
                        rows={3}
                        className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      />
                    ) : (
                      <Input
                        type={type === "date" ? "date" : "text"}
                        value={editForm[key] ?? ""}
                        onChange={(e) => setEditForm((f) => ({ ...f, [key]: e.target.value }))}
                      />
                    )}
                  </div>
                ))}
                <div className="sm:col-span-2 flex justify-end">
                  <Button type="submit" disabled={updateMutation.isPending}>
                    <Save className="mr-2 h-4 w-4" />
                    {updateMutation.isPending ? "Saving..." : "Save Changes"}
                  </Button>
                </div>
              </form>
            )}

            {activeTab === "education" && (
              <AddRecordForm
                fields={[
                  ["degree", "Degree *"],
                  ["specialization", "Specialization"],
                  ["institution", "Institution"],
                  ["board_university", "Board / University"],
                  ["pass_year", "Pass Year", "number"],
                  ["percentage_cgpa", "Percentage / CGPA", "number"],
                ]}
                form={educationForm}
                setForm={setEducationForm}
                onSubmit={(payload) => educationMutation.mutate(payload)}
                saving={educationMutation.isPending}
                submitLabel="Add Education"
                requiredFields={["degree"]}
              />
            )}

            {activeTab === "experience" && (
              <AddRecordForm
                fields={[
                  ["company_name", "Company Name *"],
                  ["designation", "Designation"],
                  ["from_date", "From Date", "date"],
                  ["to_date", "To Date", "date"],
                  ["responsibilities", "Responsibilities", "textarea"],
                ]}
                form={experienceForm}
                setForm={setExperienceForm}
                onSubmit={(payload) => experienceMutation.mutate(payload)}
                saving={experienceMutation.isPending}
                submitLabel="Add Experience"
                requiredFields={["company_name"]}
              />
            )}

            {activeTab === "skills" && (
              <AddRecordForm
                fields={[
                  ["skill_name", "Skill Name *"],
                  ["proficiency", "Proficiency"],
                  ["years_experience", "Years Experience", "number"],
                ]}
                form={skillForm}
                setForm={setSkillForm}
                onSubmit={(payload) => skillMutation.mutate(payload)}
                saving={skillMutation.isPending}
                submitLabel="Add Skill"
                requiredFields={["skill_name"]}
              />
            )}

            {activeTab === "documents" && (
              <p className="text-sm text-muted-foreground">
                Document upload is managed from the Documents section for this employee.
              </p>
            )}

            {activeTab === "account" && (
              <p className="text-sm text-muted-foreground">
                User login mapping can be managed from the Account tab below.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab content */}
      {activeTab === "360" && (
        <div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-4">
            <InsightTile icon={Star} label="Skills" value={skillCount} detail={skillCount ? "Mapped to proficiency" : "No skills yet"} />
            <InsightTile icon={FileText} label="Documents" value={documentCount} detail={documentCount ? "Profile documents" : "No documents yet"} />
            <InsightTile icon={Package} label="Assets" value={emp.asset_count || emp.assets?.length || 0} detail="Assigned and recoverable" />
            <InsightTile icon={Target} label="Performance" value={emp.performance_score || "Ready"} detail="Goals, reviews, and feedback" />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
            <Card>
              <CardHeader>
                <CardTitle>Employee 360 Timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {employee360Events.map((event, index) => (
                  <div key={`${event.title}-${index}`} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-[2.5rem_1fr_auto] sm:items-start">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <event.icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{event.title}</p>
                        <Badge variant="outline">{event.area}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{event.detail}</p>
                    </div>
                    <p className="text-xs font-medium text-muted-foreground">{event.date}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>360 Snapshot</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <SnapshotRow label="Attendance" value={emp.attendance_status || "Stable"} />
                <SnapshotRow label="Leave" value={emp.leave_balance ? `${emp.leave_balance} days balance` : "Balance ready"} />
                <SnapshotRow label="Payroll" value={emp.last_payroll_status || "Paid as per cycle"} />
                <SnapshotRow label="Tickets" value={emp.open_ticket_count ? `${emp.open_ticket_count} open` : "No open tickets"} />
                <SnapshotRow label="Assets" value={emp.asset_count ? `${emp.asset_count} assigned` : "No asset alerts"} />
                <SnapshotRow label="Documents" value={`${documentCount} records`} />
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {activeTab === "personal" && (
        <Card>
          <CardHeader><CardTitle>Personal Information</CardTitle></CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                ["Full Name", `${emp.first_name} ${emp.middle_name || ""} ${emp.last_name}`.trim()],
                ["Gender", emp.gender],
                ["Date of Birth", formatDate(emp.date_of_birth)],
                ["Marital Status", emp.marital_status],
                ["Blood Group", emp.blood_group],
                ["Nationality", emp.nationality],
                ["Category", emp.category],
                ["Emergency Contact", emp.emergency_contact_name],
                ["Emergency Phone", emp.emergency_contact_number],
                ["Interests", emp.interests],
                ["Research / Publications", emp.research_work],
              ].map(([label, value]) => (
                <div key={label as string}>
                  <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                  <dd className="text-sm mt-1">{value || "—"}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Present Address</h4>
                <p className="text-sm">{emp.present_address || "—"}</p>
                {emp.present_city && <p className="text-sm">{emp.present_city}, {emp.present_state} {emp.present_pincode}</p>}
              </div>
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Permanent Address</h4>
                <p className="text-sm">{emp.permanent_address || "—"}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "family" && (
        <Card>
          <CardHeader><CardTitle>Family Information</CardTitle></CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">{emp.family_information || "No family information added"}</p>
          </CardContent>
        </Card>
      )}

      {activeTab === "health" && (
        <Card>
          <CardHeader><CardTitle>Health Information</CardTitle></CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">{emp.health_information || "No health information added"}</p>
          </CardContent>
        </Card>
      )}

      {activeTab === "job" && (
        <Card>
          <CardHeader><CardTitle>Job Information</CardTitle></CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                ["Employee ID", emp.employee_id],
                ["Employment Type", emp.employment_type],
                ["Status", emp.status],
                ["Work Location", emp.work_location],
                ["Date of Joining", formatDate(emp.date_of_joining)],
                ["Date of Confirmation", formatDate(emp.date_of_confirmation)],
                ["Probation Period", emp.probation_period_months ? `${emp.probation_period_months} months` : "—"],
              ].map(([label, value]) => (
                <div key={label as string}>
                  <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                  <dd className="text-sm mt-1">{value || "—"}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      )}

      {activeTab === "education" && (
        <Card>
          <CardHeader><CardTitle>Education</CardTitle></CardHeader>
          <CardContent>
            {emp.educations?.length === 0 ? (
              <p className="text-muted-foreground text-sm">No education records</p>
            ) : (
              <div className="space-y-4">
                {emp.educations?.map((edu: { id: number; degree: string; institution?: string; specialization?: string; pass_year?: number; percentage_cgpa?: number }) => (
                  <div key={edu.id} className="flex items-start gap-4 p-4 rounded-lg border">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                      <GraduationCap className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-medium">{edu.degree}</p>
                      {edu.specialization && <p className="text-sm text-muted-foreground">{edu.specialization}</p>}
                      <p className="text-sm text-muted-foreground">{edu.institution}</p>
                      <p className="text-xs text-muted-foreground">{edu.pass_year} · {edu.percentage_cgpa}%</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "experience" && (
        <Card>
          <CardHeader><CardTitle>Experience</CardTitle></CardHeader>
          <CardContent>
            {emp.experiences?.length === 0 ? (
              <p className="text-muted-foreground text-sm">No experience records</p>
            ) : (
              <div className="space-y-4">
                {emp.experiences?.map((exp: { id: number; company_name: string; designation?: string; from_date?: string; to_date?: string; responsibilities?: string }) => (
                  <div key={exp.id} className="rounded-lg border p-4">
                    <p className="font-medium">{exp.company_name}</p>
                    {exp.designation && <p className="text-sm text-muted-foreground">{exp.designation}</p>}
                    <p className="text-xs text-muted-foreground">
                      {exp.from_date ? formatDate(exp.from_date) : "—"} - {exp.to_date ? formatDate(exp.to_date) : "Present"}
                    </p>
                    {exp.responsibilities && <p className="mt-3 whitespace-pre-wrap text-sm text-muted-foreground">{exp.responsibilities}</p>}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "skills" && (
        <Card>
          <CardHeader><CardTitle>Skills</CardTitle></CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {emp.skills?.length === 0 ? (
                <p className="text-muted-foreground text-sm">No skills added</p>
              ) : (
                emp.skills?.map((skill: { id: number; skill_name: string; proficiency?: string }) => (
                  <Badge key={skill.id} variant="secondary" className="text-sm">
                    {skill.skill_name}
                    {skill.proficiency && <span className="ml-1 text-xs opacity-70">· {skill.proficiency}</span>}
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "documents" && (
        <Card>
          <CardHeader><CardTitle>Documents</CardTitle></CardHeader>
          <CardContent>
            {emp.documents?.length === 0 ? (
              <p className="text-muted-foreground text-sm">No documents uploaded</p>
            ) : (
              <div className="space-y-3">
                {emp.documents?.map((doc: { id: number; document_type: string; document_name?: string; document_number?: string; is_verified?: boolean }) => (
                  <div key={doc.id} className="flex items-start justify-between gap-4 rounded-lg border p-4">
                    <div>
                      <p className="font-medium">{doc.document_name || doc.document_type}</p>
                      <p className="text-sm text-muted-foreground">{doc.document_type}</p>
                      {doc.document_number && <p className="text-xs text-muted-foreground">{doc.document_number}</p>}
                    </div>
                    <Badge variant={doc.is_verified ? "success" : "secondary"}>{doc.is_verified ? "Verified" : "Pending"}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "account" && (
        <Card>
          <CardHeader><CardTitle>User Login Mapping</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border bg-muted/30 p-4 text-sm">
              <p className="font-medium">Current login</p>
              <p className="mt-1 text-muted-foreground">
                {emp.user_id
                  ? `${linkedUser?.email || `User #${emp.user_id}`} is linked to this employee.`
                  : "No login user is linked to this employee yet."}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
              <div className="space-y-2">
                <Label>Select existing user</Label>
                <select
                  value={selectedUserId}
                  onChange={(event) => setSelectedUserId(event.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  disabled={userOptions.isLoading}
                >
                  <option value="">No linked user</option>
                  {(userOptions.data || []).map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.email}{user.role ? ` (${user.role})` : ""}{user.employee_id ? " - current" : ""}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  Only unlinked users are shown, plus the user already linked to this employee.
                </p>
              </div>
              <div className="flex items-end">
                <Button
                  type="button"
                  onClick={() => linkUserMutation.mutate(selectedUserId ? Number(selectedUserId) : null)}
                  disabled={linkUserMutation.isPending || userOptions.isLoading}
                >
                  <Link2 className="mr-2 h-4 w-4" />
                  {linkUserMutation.isPending ? "Saving..." : "Save Mapping"}
                </Button>
              </div>
              <div className="flex items-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setSelectedUserId("");
                    linkUserMutation.mutate(null);
                  }}
                  disabled={!emp.user_id || linkUserMutation.isPending}
                >
                  <Unlink className="mr-2 h-4 w-4" />
                  Unlink
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "bank" && (
        <Card>
          <CardHeader><CardTitle>Bank & Tax Details</CardTitle></CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                ["Bank Name", emp.bank_name],
                ["Account Number", emp.account_number ? `****${emp.account_number.slice(-4)}` : "—"],
                ["IFSC Code", emp.ifsc_code],
                ["Account Type", emp.account_type],
                ["PAN Number", emp.pan_number ? `****${emp.pan_number.slice(-4)}` : "—"],
                ["UAN Number", emp.uan_number],
                ["PF Number", emp.pf_number],
              ].map(([label, value]) => (
                <div key={label as string}>
                  <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                  <dd className="text-sm mt-1">{value || "—"}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

type Employee360Event = {
  area: string;
  title: string;
  detail: string;
  date: string;
  icon: React.ElementType;
};

function buildEmployee360Events(emp: Record<string, any>): Employee360Event[] {
  const events: Employee360Event[] = [
    {
      area: "Job",
      title: "Joined organization",
      detail: `${emp.employment_type || "Employee"} at ${emp.work_location || "assigned work location"}`,
      date: formatDate(emp.date_of_joining),
      icon: Briefcase,
    },
    {
      area: "Payroll",
      title: "Payroll history",
      detail: emp.last_payroll_status || "Monthly payroll history and payslip status available from Payroll",
      date: emp.last_payroll_date ? formatDate(emp.last_payroll_date) : "Current cycle",
      icon: Banknote,
    },
    {
      area: "Attendance",
      title: "Attendance signal",
      detail: emp.attendance_status || "Attendance, late marks, and regularization signals tracked",
      date: "Live",
      icon: Clock,
    },
    {
      area: "Leave",
      title: "Leave position",
      detail: emp.leave_balance ? `${emp.leave_balance} days available` : "Leave balance and approvals connected",
      date: "Live",
      icon: CalendarDays,
    },
    {
      area: "Performance",
      title: "Performance profile",
      detail: emp.performance_score ? `Latest score ${emp.performance_score}` : "Goals, review cycles, and 360 feedback visible",
      date: "Latest cycle",
      icon: Target,
    },
    {
      area: "Helpdesk",
      title: "Support tickets",
      detail: emp.open_ticket_count ? `${emp.open_ticket_count} open tickets require attention` : "No open support blockers",
      date: "Live",
      icon: HelpCircle,
    },
  ];

  (emp.skills || []).slice(0, 3).forEach((skill: { skill_name?: string; proficiency?: string }) => {
    events.push({
      area: "Skills",
      title: skill.skill_name || "Skill",
      detail: skill.proficiency ? `${skill.proficiency} proficiency` : "Skill mapped to employee profile",
      date: "Profile",
      icon: Star,
    });
  });

  (emp.documents || []).slice(0, 3).forEach((doc: { document_name?: string; document_type?: string; is_verified?: boolean }) => {
    events.push({
      area: "Documents",
      title: doc.document_name || doc.document_type || "Document",
      detail: doc.is_verified ? "Verified document" : "Pending verification",
      date: "Profile",
      icon: FileText,
    });
  });

  return events;
}

function InsightTile({ icon: Icon, label, value, detail }: { icon: React.ElementType; label: string; value: string | number; detail: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="rounded-lg bg-primary/10 p-2 text-primary"><Icon className="h-4 w-4" /></div>
        <div>
          <p className="text-xl font-semibold">{value}</p>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="text-xs text-muted-foreground">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function SnapshotRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border p-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function AddRecordForm({
  fields,
  form,
  setForm,
  onSubmit,
  saving,
  submitLabel,
  requiredFields = [],
}: {
  fields: Array<[string, string, string?]>;
  form: Record<string, any>;
  setForm: (form: Record<string, any>) => void;
  onSubmit: (payload: Record<string, any>) => void;
  saving: boolean;
  submitLabel: string;
  requiredFields?: string[];
}) {
  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault();
        const payload = { ...form };
        Object.keys(payload).forEach((key) => {
          if (payload[key] === "") payload[key] = null;
          if (["pass_year", "years_experience", "percentage_cgpa"].includes(key) && payload[key] != null) payload[key] = Number(payload[key]);
        });
        const missingField = requiredFields.find((key) => !String(payload[key] || "").trim());
        if (missingField) {
          const label = fields.find(([key]) => key === missingField)?.[1]?.replace(" *", "") || "Required field";
          toast({
            title: `${label} is required`,
            description: "Please fill the required field before saving.",
            variant: "destructive",
          });
          return;
        }
        const invalidNumber = ["pass_year", "years_experience", "percentage_cgpa"].find((key) => Number.isNaN(payload[key]));
        if (invalidNumber) {
          const label = fields.find(([key]) => key === invalidNumber)?.[1] || "Number";
          toast({
            title: `${label} is invalid`,
            description: "Please enter a valid number.",
            variant: "destructive",
          });
          return;
        }
        onSubmit(payload);
      }}
    >
      {fields.map(([key, label, type]) => (
        <div key={key} className={`space-y-2 ${type === "textarea" ? "sm:col-span-2" : ""}`}>
          <Label>{label}</Label>
          {type === "textarea" ? (
            <textarea
              value={form[key] ?? ""}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              rows={3}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          ) : (
            <Input
              type={type === "date" || type === "number" ? type : "text"}
              step={type === "number" ? "0.1" : undefined}
              value={form[key] ?? ""}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          )}
        </div>
      ))}
      <div className="sm:col-span-2 flex justify-end">
        <Button type="submit" disabled={saving}>
          <Save className="mr-2 h-4 w-4" />
          {saving ? "Saving..." : submitLabel}
        </Button>
      </div>
    </form>
  );
}
