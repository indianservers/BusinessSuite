import { PhoneInput } from "@/lib/validation/PhoneInput";
import { phoneError, textError } from "@/lib/validation";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, BookOpen, Check, ChevronLeft, ChevronRight, HeartPulse, Loader2, Plus, Save, Settings, Users, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { employeeApi, companyApi, attendanceApi } from "@/services/api";
import { toast } from "@/hooks/use-toast";
import { loadManagerOptions } from "./employeeJobOptions";
import { usePageTitle } from "@/hooks/use-page-title";

const schema = z.object({
  first_name: z.string().trim().min(1, "First name is required").max(160).refine(value=>!textError(value,160),"Enter a valid name without control characters"),
  last_name: z.string().trim().max(160).refine(value=>!textError(value,160,false),"Enter a valid name without control characters"),
  gender: z.string().optional(),
  date_of_birth: z.preprocess((v) => v === "" ? undefined : v, z.string().optional()),
  date_of_joining: z.string().min(1, "Joining date is required"),
  employment_type: z.string().default("Full-time"),
  branch_id: z.preprocess((v) => v === "" || Number.isNaN(v) ? null : v, z.number().optional().nullable()),
  department_id: z.preprocess((v) => v === "" || Number.isNaN(v) ? null : v, z.number().optional().nullable()),
  reporting_manager_id: z.preprocess((v) => v === "" || Number.isNaN(v) ? null : v, z.number().optional().nullable()),
  designation_id: z.preprocess((v) => v === "" || Number.isNaN(v) ? null : v, z.number().optional().nullable()),
  personal_email: z.string().email("Invalid email").optional().or(z.literal("")),
  phone_number: z.string().optional(),
  phone_number_country_code: z.string().optional(),
  alternate_phone: z.string().optional(),
  alternate_phone_country_code: z.string().optional(),
  emergency_contact_name: z.string().optional(),
  emergency_contact_number: z.string().optional(),
  emergency_contact_number_country_code: z.string().optional(),
  emergency_contact_relation: z.string().optional(),
  present_address: z.string().optional(),
  permanent_address: z.string().optional(),
  present_city: z.string().optional(),
  present_state: z.string().optional(),
  present_pincode: z.string().optional(),
  bank_name: z.string().optional(),
  bank_branch: z.string().optional(),
  account_number: z.string().optional(),
  ifsc_code: z.string().optional(),
  pan_number: z.string().optional(),
  aadhaar_number: z.string().optional(),
  uan_number: z.string().optional(),
  pf_number: z.string().optional(),
  esic_number: z.string().optional(),
  bio: z.string().optional(),
  interests: z.string().optional(),
  research_work: z.string().optional(),
  family_information: z.string().optional(),
  health_information: z.string().optional(),
  shift_id: z.preprocess((v) => v === "" || Number.isNaN(v) ? null : v, z.number().optional().nullable()),
  create_user_account: z.boolean().default(false),
  user_email: z.string().email().optional().or(z.literal("")),
  user_password: z.string().optional(),
}).superRefine((data,context)=>{
  for(const field of ['phone_number','alternate_phone','emergency_contact_number'] as const){const message=phoneError(data[field],data[`${field}_country_code`]);if(message)context.addIssue({code:'custom',path:[field],message});}
  if(data.date_of_birth&&data.date_of_birth>=new Date().toLocaleDateString("en-CA"))context.addIssue({code:"custom",path:["date_of_birth"],message:"Date of birth must be in the past"});
  if(!data.create_user_account)return;
  if(!data.user_email)context.addIssue({code:'custom',path:['user_email'],message:'Login email is required'});
  if(!data.user_password||data.user_password.length<12||new TextEncoder().encode(data.user_password).length>72)
    context.addIssue({code:'custom',path:['user_password'],message:'Use at least 12 characters and no more than 72 UTF-8 bytes'});
});

type FormData = z.infer<typeof schema>;

const steps = ["Personal", "Job", "Contact", "Optional", "Account"];
type QuickType = "company" | "branch" | "department" | "designation" | "shift";

const stepFields: Array<Array<keyof FormData>> = [
  ["first_name", "last_name", "gender", "date_of_birth"],
  ["date_of_joining", "employment_type", "branch_id", "department_id", "designation_id", "reporting_manager_id", "shift_id"],
  [
    "personal_email",
    "phone_number",
    "alternate_phone",
    "emergency_contact_name",
    "emergency_contact_number",
    "emergency_contact_relation",
    "present_address",
    "present_city",
    "present_state",
    "present_pincode",
  ],
  [
    "bio",
    "interests",
    "research_work",
    "family_information",
    "health_information",
    "bank_name",
    "bank_branch",
    "account_number",
    "ifsc_code",
    "pan_number",
    "aadhaar_number",
    "uan_number",
    "pf_number",
    "esic_number",
  ],
  ["create_user_account", "user_email", "user_password"],
];

export default function AddEmployeePage() {
  const submitting=useRef(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentStep, setCurrentStep] = useState(0);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    profile: true,
    education: false,
    family: false,
    health: false,
    bank: false,
  });
  const [quickType, setQuickType] = useState<QuickType | null>(null);
  const [quickForm, setQuickForm] = useState<Record<string, any>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data: managers = [] } = useQuery({ queryKey: ["employee-manager-options"], queryFn: loadManagerOptions });

  const { data: branches } = useQuery({
    queryKey: ["branches"],
    queryFn: () => companyApi.listBranches().then((r) => r.data),
  });

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: () => companyApi.listDepartments().then((r) => r.data),
  });

  const { data: designations } = useQuery({
    queryKey: ["designations"],
    queryFn: () => companyApi.listDesignations().then((r) => r.data),
  });

  const { data: companies, refetch: refetchCompanies } = useQuery({
    queryKey: ["companies"],
    queryFn: () => companyApi.listCompanies().then((r) => r.data),
  });

  const { data: shifts, refetch: refetchShifts } = useQuery({
    queryKey: ["shifts"],
    queryFn: () => attendanceApi.listShifts().then((r) => r.data),
  });

  const {
    register,
    trigger,
    setError: setFieldError,
    getFieldState,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<z.input<typeof schema>, unknown, FormData>({
    resolver: zodResolver(schema),
    defaultValues: { employment_type: "Full-time", create_user_account: false, last_name: "", phone_number_country_code: "+91", alternate_phone_country_code: "+91", emergency_contact_number_country_code: "+91" },
    mode: "onBlur",
  });

  const selectedBranch = watch("branch_id");
  const selectedDepartment = watch("department_id");
  const filteredDepartments = (departments || []).filter((d: any) => !selectedBranch || d.branch_id === selectedBranch);
  const filteredDesignations = (designations || []).filter((d: any) => !selectedDepartment || d.department_id === selectedDepartment);

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      employeeApi.create(cleanEmployeePayload(data)),
    onSuccess: (res) => {
      setSubmitError(null);
      toast({ title: "Employee created successfully!", variant: "default" });
      navigate(`/hrms/employees/${res.data.id}`);
    },
    onSettled: ()=>{submitting.current=false;},
    onError: (err: unknown) => {
      const details=(err as {response?:{data?:{detail?:Array<{loc?:string[];msg?:string}>}}})?.response?.data?.detail;
      if(Array.isArray(details)){
        const fields=details.map(item=>String(item.loc?.at(-1)||''));
        for(const item of details){const key=String(item.loc?.at(-1)||'') as keyof FormData;if(key)setFieldError(key,{type:'server',message:item.msg||'Invalid value'});}
        const index=stepFields.findIndex(step=>step.some(field=>fields.includes(field)));if(index>=0)setCurrentStep(index);
      }
      const message = getEmployeeErrorMessage(err);
      setSubmitError(message);
      toast({ title: "Failed to create employee", description: message, variant: "destructive" });
    },
  });

  const quickMutation = useMutation({
    mutationFn: async ({ type, data }: { type: QuickType; data: Record<string, any> }) => {
      if (type === "company") return companyApi.createCompany(data);
      if (type === "branch") return companyApi.createBranch({ ...data, company_id: Number(data.company_id) });
      if (type === "department") return companyApi.createDepartment({ ...data, branch_id: Number(data.branch_id) });
      if (type === "designation") return companyApi.createDesignation({ ...data, department_id: Number(data.department_id), level: Number(data.level || 1) });
      return attendanceApi.createShift({ ...data, grace_minutes: Number(data.grace_minutes || 10), working_hours: String(data.working_hours || "8.0") });
    },
    onSuccess: async (_, { type }) => {
      toast({ title: "Added to settings" });
      if (type === "company") await refetchCompanies();
      if (type === "branch") await queryClient.invalidateQueries({ queryKey: ["branches"] });
      if (type === "department") await queryClient.invalidateQueries({ queryKey: ["departments"] });
      if (type === "designation") await queryClient.invalidateQueries({ queryKey: ["designations"] });
      if (type === "shift") await refetchShifts();
      setQuickType(null);
      setQuickForm({});
    },
    onError: (err: any) => toast({ title: "Could not add setting", description: err?.response?.data?.detail || "Check required fields", variant: "destructive" }),
  });

  const goToStep = async (target: number) => {
    if(target>currentStep){
      for(let index=0;index<target;index++){
        if(!await trigger(stepFields[index],{shouldFocus:true})){
          setCurrentStep(index);
          const messages=stepFields[index].map(field=>getFieldState(field).error?.message).filter(Boolean);
          setSubmitError(messages.join('; ') || 'Complete the highlighted fields before continuing.');
          const first=stepFields[index].find(field=>getFieldState(field).invalid);
          if(first)requestAnimationFrame(()=>document.querySelector<HTMLInputElement>(`[name="${first}"]`)?.focus());
          return;
        }
      }
    }
    setSubmitError(null);
    setCurrentStep(target);
  };

  const onSubmit = (data: FormData) => {
    if(submitting.current)return;
    submitting.current=true;
    setSubmitError(null);
    mutation.mutate(data);
  };

  const jumpToFirstInvalidStep = (formErrors: typeof errors) => {
    const invalidFields = Object.keys(formErrors) as Array<keyof FormData>;
    const stepIndex = stepFields.findIndex((fields) => fields.some((field) => invalidFields.includes(field)));
    if (stepIndex >= 0) setCurrentStep(stepIndex);
  };

  const openQuick = (type: QuickType) => {
    const defaults: Record<QuickType, Record<string, any>> = {
      company: { country: "India" },
      branch: { company_id: companies?.[0]?.id || "", country: "India" },
      department: { branch_id: selectedBranch || branches?.[0]?.id || "" },
      designation: { department_id: selectedDepartment || departments?.[0]?.id || "", level: 1 },
      shift: { start_time: "09:30", end_time: "18:30", grace_minutes: 10, working_hours: "8.0" },
    };
    setQuickForm(defaults[type]);
    setQuickType(type);
  };

  const toggleSection = (key: string) => setOpenSections((s) => ({ ...s, [key]: !s[key] }));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/hrms/employees")}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
        <div>
          <h1 className="page-title">Add New Employee</h1>
          <p className="page-description">Create a new employee record. Empty branch or designation lists can be managed from Settings.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => navigate("/hrms/settings")} className="ml-auto">
          <Settings className="mr-2 h-4 w-4" />
          Settings
        </Button>
      </div>

      {/* Step indicator */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card p-3">
        {steps.map((step, i) => (
          <div key={step} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void goToStep(i)}
              className={`flex min-h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium transition-colors ${
                i === currentStep
                  ? "border-primary bg-primary text-primary-foreground"
                  : i < currentStep
                  ? "border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-300"
                  : "border-border bg-background text-muted-foreground hover:bg-muted"
              }`}
              aria-current={i === currentStep ? "step" : undefined}
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-background/80 text-xs text-foreground">
                {i < currentStep ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </span>
              <span>{step}</span>
            </button>
            {i < steps.length - 1 && (
              <div className={`hidden h-px w-5 sm:block ${i < currentStep ? "bg-green-500" : "bg-border"}`} />
            )}
          </div>
        ))}
      </div>

      <form
        onSubmit={handleSubmit(onSubmit, (formErrors) => {
          jumpToFirstInvalidStep(formErrors);
          const firstError = Object.values(formErrors)[0]?.message;
          toast({
            title: "Please check employee details",
            description: String(firstError || "Some required or optional fields are invalid."),
            variant: "destructive",
          });
        })}
      >
        {submitError && (
          <div role="alert" className="mb-4 flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Check employee details</p>
              <p className="mt-1">{submitError}</p>
            </div>
          </div>
        )}
        {/* Step 0: Personal Info */}
        {currentStep === 0 && (
          <Card>
            <CardHeader><CardTitle>Personal Information</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="employee-first_name">First Name *</Label>
                <Input id="employee-first_name" aria-invalid={!!errors.first_name} aria-describedby={errors.first_name ? "employee-first_name-error" : undefined} {...register("first_name")} placeholder="John" />
                {errors.first_name && <p id="employee-first_name-error" role="alert" className="text-xs text-destructive">{errors.first_name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="employee-last_name">Last Name (optional)</Label>
                <Input id="employee-last_name" aria-invalid={!!errors.last_name} aria-describedby={errors.last_name ? "employee-last_name-error" : undefined} {...register("last_name")} placeholder="Doe" />
                {errors.last_name && <p id="employee-last_name-error" role="alert" className="text-xs text-destructive">{errors.last_name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label>Gender</Label>
                <select {...register("gender")} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select Gender</option>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option><option value="Prefer not to say">Prefer not to say</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="employee-date_of_birth">Date of Birth</Label>
                <Input id="employee-date_of_birth" aria-invalid={!!errors.date_of_birth} aria-describedby={errors.date_of_birth ? "employee-date_of_birth-error" : undefined} type="date" {...register("date_of_birth")} />
                {errors.date_of_birth && <p id="employee-date_of_birth-error" role="alert" className="text-xs text-destructive">{errors.date_of_birth.message}</p>}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 1: Job Details */}
        {currentStep === 1 && (
          <Card>
            <CardHeader><CardTitle>Job Details</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="employee-date_of_joining">Date of Joining *</Label>
                <Input id="employee-date_of_joining" aria-invalid={!!errors.date_of_joining} aria-describedby={errors.date_of_joining ? "employee-date_of_joining-error" : undefined} type="date" {...register("date_of_joining")} />
                {errors.date_of_joining && <p id="employee-date_of_joining-error" role="alert" className="text-xs text-destructive">{errors.date_of_joining.message}</p>}
              </div>
              <div className="space-y-2">
                <Label>Employment Type</Label>
                <select {...register("employment_type")} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="Full-time">Full-time</option>
                  <option value="Part-time">Part-time</option>
                  <option value="Contract">Contract</option>
                  <option value="Intern">Intern</option>
                </select>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label>Branch</Label>
                  <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => openQuick("branch")}>
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <select
                  {...register("branch_id", { onChange: () => { setValue("department_id", null); setValue("designation_id", null); }, setValueAs: (v) => v === "" ? null : Number(v) })}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select Branch</option>
                  {branches?.map((b: { id: number; name: string }) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
                {errors.branch_id && <p className="text-xs text-destructive">{errors.branch_id.message}</p>}
                {!branches?.length && <p className="text-xs text-muted-foreground">No branches yet. Add one here or in Settings.</p>}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label>Department</Label>
                  <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => openQuick("department")}>
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <select
                  {...register("department_id", { onChange: () => setValue("designation_id", null), setValueAs: (v) => v === "" ? null : Number(v) })}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select Department</option>
                  {filteredDepartments?.map((d: { id: number; name: string }) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
                {errors.department_id && <p className="text-xs text-destructive">{errors.department_id.message}</p>}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label>Designation</Label>
                  <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => openQuick("designation")}>
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <select
                  {...register("designation_id", { setValueAs: (v) => v === "" ? null : Number(v) })}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select Designation</option>
                  {filteredDesignations?.map((d: { id: number; name: string }) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
                {errors.designation_id && <p className="text-xs text-destructive">{errors.designation_id.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="reporting-manager">Reporting Manager / Intern Supervisor</Label>
                <select id="reporting-manager" {...register("reporting_manager_id", { setValueAs: (v) => v === "" ? null : Number(v) })} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Unassigned</option>
                  {managers.map((manager) => <option key={manager.id} value={manager.id}>{manager.name}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label>Shift</Label>
                  <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => openQuick("shift")}>
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <select {...register("shift_id", { setValueAs: (v) => v === "" ? null : Number(v) })} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select Shift</option>
                  {shifts?.map((s: { id: number; name: string; start_time: string; end_time: string }) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.start_time}-{s.end_time})</option>
                  ))}
                </select>
                {errors.shift_id && <p className="text-xs text-destructive">{errors.shift_id.message}</p>}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Contact */}
        {currentStep === 2 && (
          <Card>
            <CardHeader><CardTitle>Contact Information</CardTitle></CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="employee-personal_email">Personal Email</Label>
                <Input id="employee-personal_email" aria-invalid={!!errors.personal_email} aria-describedby={errors.personal_email ? "employee-personal_email-error" : undefined} type="email" {...register("personal_email")} placeholder="john@example.com" />
                {errors.personal_email && <p id="employee-personal_email-error" role="alert" className="text-xs text-destructive">{errors.personal_email.message}</p>}
              </div>
              <div className="space-y-2">
                <Label>Phone Number</Label>
                <PhoneInput label="Phone Number" name="phone_number" value={watch("phone_number") || ""} countryCode={watch("phone_number_country_code") || ""} onChange={value=>setValue("phone_number",value,{shouldValidate:true})} onCountryCodeChange={value=>setValue("phone_number_country_code",value,{shouldValidate:true})} error={errors.phone_number?.message} />
              </div>
              <div className="space-y-2">
                <Label>Alternate Phone</Label>
                <PhoneInput label="Alternate Phone" name="alternate_phone" value={watch("alternate_phone") || ""} countryCode={watch("alternate_phone_country_code") || ""} onChange={value=>setValue("alternate_phone",value,{shouldValidate:true})} onCountryCodeChange={value=>setValue("alternate_phone_country_code",value,{shouldValidate:true})} error={errors.alternate_phone?.message} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="employee-emergency_contact_name">Emergency Contact</Label>
                <Input id="employee-emergency_contact_name" aria-invalid={!!errors.emergency_contact_name} aria-describedby={errors.emergency_contact_name ? "employee-emergency_contact_name-error" : undefined} {...register("emergency_contact_name")} placeholder="Contact name" />
              </div>
              <div className="space-y-2">
                <Label>Emergency Phone</Label>
                <PhoneInput label="Emergency Phone" name="emergency_contact_number" value={watch("emergency_contact_number") || ""} countryCode={watch("emergency_contact_number_country_code") || ""} onChange={value=>setValue("emergency_contact_number",value,{shouldValidate:true})} onCountryCodeChange={value=>setValue("emergency_contact_number_country_code",value,{shouldValidate:true})} error={errors.emergency_contact_number?.message} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="employee-emergency_contact_relation">Relation</Label>
                <Input id="employee-emergency_contact_relation" aria-invalid={!!errors.emergency_contact_relation} aria-describedby={errors.emergency_contact_relation ? "employee-emergency_contact_relation-error" : undefined} {...register("emergency_contact_relation")} placeholder="Spouse, parent, friend" />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label>Present Address</Label>
                <textarea {...register("present_address")} rows={3} className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
              </div>
              <div className="grid gap-4 sm:col-span-2 sm:grid-cols-3">
                <Field label="City"><Input {...register("present_city")} /></Field>
                <Field label="State"><Input {...register("present_state")} /></Field>
                <Field label="Pincode"><Input {...register("present_pincode")} /></Field>
              </div>
            </CardContent>
          </Card>
        )}

        {currentStep === 3 && (
          <div className="space-y-4">
            <OptionalSection
              icon={BookOpen}
              title="Profile, Interests & Research"
              open={openSections.profile}
              onToggle={() => toggleSection("profile")}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Bio"><textarea {...register("bio")} rows={4} className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></Field>
                <Field label="Interests"><textarea {...register("interests")} rows={4} placeholder="AI, analytics, community work..." className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" /></Field>
                <Field label="Research / Publications"><textarea {...register("research_work")} rows={4} className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm sm:col-span-2" /></Field>
              </div>
            </OptionalSection>
            <OptionalSection icon={Users} title="Family Information" open={openSections.family} onToggle={() => toggleSection("family")}>
              <textarea {...register("family_information")} rows={4} placeholder="Dependents, spouse, children, nominee notes..." className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
            </OptionalSection>
            <OptionalSection icon={HeartPulse} title="Health Information" open={openSections.health} onToggle={() => toggleSection("health")}>
              <textarea {...register("health_information")} rows={4} placeholder="Allergies, conditions, accessibility needs, insurance notes..." className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
            </OptionalSection>
            <OptionalSection icon={Save} title="Bank & Compliance" open={openSections.bank} onToggle={() => toggleSection("bank")}>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Bank Name"><Input {...register("bank_name")} /></Field>
                <Field label="Branch"><Input {...register("bank_branch")} /></Field>
                <Field label="Account Number"><Input {...register("account_number")} /></Field>
                <Field label="IFSC Code"><Input {...register("ifsc_code")} /></Field>
                <Field label="PAN"><Input {...register("pan_number")} /></Field>
                <Field label="Aadhaar"><Input {...register("aadhaar_number")} /></Field>
                <Field label="UAN"><Input {...register("uan_number")} /></Field>
                <Field label="PF Number"><Input {...register("pf_number")} /></Field>
                <Field label="ESIC Number"><Input {...register("esic_number")} /></Field>
              </div>
            </OptionalSection>
          </div>
        )}

        {/* Step 3: Account */}
        {currentStep === 4 && (
          <Card>
            <CardHeader><CardTitle>User Account (Optional)</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
                <input
                  type="checkbox"
                  id="create_user"
                  {...register("create_user_account")}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <label htmlFor="create_user" className="text-sm font-medium cursor-pointer">
                  Create login account for this employee
                </label>
              </div>
              {watch("create_user_account") && (
                <div className="space-y-2">
                  <Label htmlFor="employee-login-email">Login Email *</Label>
                  <Input id="employee-login-email" type="email" {...register("user_email")} placeholder="employee@company.com" />
                  {errors.user_email&&<p className="text-xs text-destructive">{errors.user_email.message}</p>}
                  <Label htmlFor="employee-login-password">Login Password *</Label>
                  <Input id="employee-login-password" type="password" autoComplete="new-password" maxLength={72} {...register("user_password")} />
                  {errors.user_password&&<p className="text-xs text-destructive">{errors.user_password.message}</p>}
                  <p className="text-xs text-muted-foreground">Set a unique password of at least 12 characters that meets your organization’s password policy.</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Navigation buttons */}
        <div className="flex items-center justify-between mt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}
            disabled={currentStep === 0}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>

          {currentStep < steps.length - 1 ? (
            <Button
              type="button"
              key="next-step"
              onClick={event => { event.preventDefault(); void goToStep(Math.min(steps.length - 1,currentStep+1)); }}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button key="create-employee" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Create Employee
            </Button>
          )}
        </div>
      </form>
      {quickType && (
        <QuickCreateModal
          type={quickType}
          form={quickForm}
          setForm={setQuickForm}
          companies={companies || []}
          branches={branches || []}
          departments={departments || []}
          onClose={() => setQuickType(null)}
          onSubmit={(e) => {
            e.preventDefault();
            quickMutation.mutate({ type: quickType, data: quickForm });
          }}
          saving={quickMutation.isPending}
        />
      )}
    </div>
  );
}

function cleanEmployeePayload(data: FormData) {
  const payload: Record<string, any> = { ...data };
  ["date_of_birth", "date_of_confirmation"].forEach((key) => {
    if (payload[key] === "") payload[key] = null;
  });
  ["branch_id", "department_id", "designation_id", "reporting_manager_id", "shift_id"].forEach((key) => {
    if (payload[key] === "" || Number.isNaN(payload[key])) payload[key] = null;
  });
  Object.keys(payload).forEach((key) => {
    if (payload[key] === "") payload[key] = undefined;
  });
  return payload;
}

function getEmployeeErrorMessage(error: unknown) {
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
    return Object.entries(detail)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
      .join("; ");
  }

  return (error as { message?: string })?.message || "Failed to create employee. Please check the required details and try again.";
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function OptionalSection({ icon: Icon, title, open, onToggle, children }: { icon: React.ElementType; title: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <Card>
      <button type="button" onClick={onToggle} className="flex w-full items-center justify-between p-4 text-left">
        <span className="flex items-center gap-3 font-semibold"><Icon className="h-4 w-4 text-primary" />{title}</span>
        <ChevronRight className={`h-4 w-4 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {open && <CardContent className="border-t pt-4">{children}</CardContent>}
    </Card>
  );
}

function QuickCreateModal({
  type,
  form,
  setForm,
  companies,
  branches,
  departments,
  onClose,
  onSubmit,
  saving,
}: {
  type: QuickType;
  form: Record<string, any>;
  setForm: (v: Record<string, any>) => void;
  companies: any[];
  branches: any[];
  departments: any[];
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
  saving: boolean;
}) {
  const update = (key: string, value: any) => setForm({ ...form, [key]: value });
  const select = (key: string, options: any[]) => (
    <select value={form[key] || ""} onChange={(e) => update(key, e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
      <option value="">Select</option>
      {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
    </select>
  );
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4">
      <form onSubmit={onSubmit} className="w-full max-w-xl rounded-t-lg border bg-background shadow-xl sm:rounded-lg">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="font-semibold">Add {type}</h2>
          <Button type="button" variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Field label="Name *"><Input list={type === "designation" ? "designation-suggestions" : undefined} value={form.name || ""} onChange={(e) => update("name", e.target.value)} /></Field>
          <datalist id="designation-suggestions">{["Intern", "Software Architect", "Marketing"].map((name) => <option key={name} value={name} />)}</datalist>
          {type !== "company" && type !== "shift" && <Field label="Code"><Input value={form.code || ""} onChange={(e) => update("code", e.target.value)} /></Field>}
          {type === "branch" && <Field label="Company *">{select("company_id", companies)}</Field>}
          {type === "department" && <Field label="Branch *">{select("branch_id", branches)}</Field>}
          {type === "designation" && <Field label="Department *">{select("department_id", departments)}</Field>}
          {type === "designation" && <Field label="Level"><Input type="number" min={1} value={form.level || 1} onChange={(e) => update("level", e.target.value)} /></Field>}
          {type === "shift" && <><Field label="Start"><Input type="time" value={form.start_time || ""} onChange={(e) => update("start_time", e.target.value)} /></Field><Field label="End"><Input type="time" value={form.end_time || ""} onChange={(e) => update("end_time", e.target.value)} /></Field><Field label="Grace Minutes"><Input type="number" value={form.grace_minutes || 10} onChange={(e) => update("grace_minutes", e.target.value)} /></Field><Field label="Working Hours"><Input type="number" step="0.5" value={form.working_hours || "8.0"} onChange={(e) => update("working_hours", e.target.value)} /></Field></>}
          {(type === "company" || type === "branch") && <><Field label="Email"><Input value={form.email || ""} onChange={(e) => update("email", e.target.value)} /></Field><Field label="City"><Input value={form.city || ""} onChange={(e) => update("city", e.target.value)} /></Field></>}
        </div>
        <div className="flex justify-end gap-2 border-t px-5 py-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
        </div>
      </form>
    </div>
  );
}
