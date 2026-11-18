import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./lms-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import { standardRecordGroups } from "@/shared/data-grid/record-group-fields";
import { NativeSelect } from "@/components/ui/native-select";
import CourseCurriculum from "./CourseCurriculum";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, BookOpenCheck, GraduationCap, Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { lmsApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

type Course = {
  id: number;
  code: string;
  title: string;
  category?: string;
  delivery_mode: string;
  duration_hours: string | number;
  content_standard?: string;
  external_launch_url?: string;
  scorm_version?: string;
  xapi_activity_id?: string;
  is_mandatory: boolean;
};

type Assignment = {
  id: number;
  course_id: number;
  employee_id: number;
  status: string;
  due_date?: string;
  score?: string | number;
};

type Certification = {
  id: number;
  employee_id: number;
  title: string;
  status: string;
  expires_on?: string;
  renewal_required?: boolean;
  renewal_status?: string;
  renewal_due_on?: string;
};

type CertificationRenewal = {
  id: number;
  certification_id: number;
  employee_id: number;
  due_on: string;
  status: string;
  reminder_sent_at?: string;
};

export default function LMSPage() {
  const [outlineCourse,setOutlineCourse]=useState<number|null>(null);
  usePageTitle("Learning");
  const phone = useMobile(480);
  const qc = useQueryClient();
  const [showCourseForm, setShowCourseForm] = useState(false);
  const [courseForm, setCourseForm] = useState({
    code: "",
    title: "",
    category: "Compliance",
    delivery_mode: "Online",
    duration_hours: "1",
    content_standard: "Internal",
    external_launch_url: "",
    scorm_version: "",
    xapi_activity_id: "",
    is_mandatory: true,
  });

  const coursesQuery = useQuery({
    queryKey: ["lms-courses"],
    queryFn: () => lmsApi.courses().then((r) => r.data as Course[]),
  });
  const assignmentsQuery = useQuery({
    queryKey: ["lms-assignments"],
    queryFn: () => lmsApi.assignments().then((r) => r.data as Assignment[]),
  });
  const certificationsQuery = useQuery({
    queryKey: ["lms-certifications"],
    queryFn: () => lmsApi.certifications().then((r) => r.data as Certification[]),
    enabled: false,
    retry: false,
  });
  const renewalsQuery = useQuery({
    queryKey: ["lms-certification-renewals"],
    queryFn: () => lmsApi.certificationRenewals({ due_within_days: 90 }).then((r) => r.data as CertificationRenewal[]),
    enabled: false,
    retry: false,
  });

  const { data: courses, isLoading } = coursesQuery;
  const { data: assignments } = assignmentsQuery;
  const { data: certifications } = certificationsQuery;
  const { data: renewals } = renewalsQuery;

  const createCourse = useMutation({
    mutationFn: () =>
      lmsApi.createCourse({
        ...courseForm,
        duration_hours: Number(courseForm.duration_hours || 0),
      }),
    onSuccess: () => {
      toast({ title: "Course published" });
      setShowCourseForm(false);
      setCourseForm({
        code: "",
        title: "",
        category: "Compliance",
        delivery_mode: "Online",
        duration_hours: "1",
        content_standard: "Internal",
        external_launch_url: "",
        scorm_version: "",
        xapi_activity_id: "",
        is_mandatory: true,
      });
      qc.invalidateQueries({ queryKey: ["lms-courses"] });
    },
    onError: () => toast({ title: "Unable to publish course", variant: "destructive" }),
  });

  const completed = (assignments || []).filter((item) => item.status === "Completed").length;
  const pending = (assignments || []).filter((item) => item.status !== "Completed").length;
  const courseTitleById = new Map((courses || []).map((course) => [course.id, course.title]));
  const expiring = (certifications || []).filter((cert) => {
    if (!cert.expires_on) return false;
    const days = (new Date(cert.expires_on).getTime() - Date.now()) / 86400000;
    return days >= 0 && days <= 45;
  }).length;
  const dueRenewals = (renewals || []).filter((renewal) => renewal.status !== "Completed").length;

  return (
    <div className="hrms-lms-page space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">Learning Management</h1>
          <p className="page-description">Courses, employee assignments, mandatory training, certifications, and renewal tracking.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => phone ? void Promise.all([coursesQuery.refetch(), assignmentsQuery.refetch()]) : qc.invalidateQueries({ queryKey: ["lms-courses"] })}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCourseForm((value) => !value)}>
            <Plus className="mr-2 h-4 w-4" />
            New Course
          </Button>
        </div>
      </div>

      {phone && [coursesQuery, assignmentsQuery].some(query => query.isError) && <p role="alert" className="text-sm text-destructive">Learning information could not load. <Button variant="outline" onClick={() => { for (const query of [coursesQuery, assignmentsQuery]) if (query.isError) void query.refetch(); }}>Retry learning</Button></p>}
      <details className="hrms-lms-outline rounded-lg border bg-card p-4"><summary>Arrange course sections and lessons</summary><GroupedRecords scope="apps/hrms/pages/lms/LMSPage:cards-1" items={(courses) || []} fields={standardRecordGroups((courses) || [])} gridClassName="space-y-4 mt-4" renderItem={course => <details key={course.id} className="rounded border p-3" onToggle={e=>{if(e.currentTarget.open)setOutlineCourse(course.id);}}><summary>{course.title}</summary>{outlineCourse===course.id&&<CourseCurriculum courseId={course.id} />}</details>}/></details>
      <div className="hrms-lms-kpis grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Courses", value: phone && courses === undefined ? "—" : courses?.length || 0, icon: GraduationCap },
          { label: "Pending Assignments", value: phone && assignments === undefined ? "—" : pending, icon: BookOpenCheck },
          { label: "Completed", value: phone && assignments === undefined ? "—" : completed, icon: Award },
          { label: "Certificates Expiring", value: phone && certifications === undefined ? "—" : expiring, icon: RefreshCw },
          { label: "Renewals Due", value: phone && renewals === undefined ? "—" : dueRenewals, icon: Award },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label}>
              <CardContent className="p-5">
                <Icon className="mb-3 h-5 w-5 text-primary" />
                <p className="text-2xl font-semibold">{item.value}</p>
                <p className="text-sm text-muted-foreground">{item.label}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {showCourseForm && (
        <Card className="hrms-lms-create-shell">
          <CardHeader>
            <CardTitle className="text-base">Publish Course</CardTitle>
            <CardDescription>Create a course that HR can assign by employee or role.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <SmartCreateSection title="Publish Course" autoOpen onClose={() => setShowCourseForm(false)} size="standard" mobileSheet={phone}><div className="hrms-lms-course-fields space-y-4">{phone && <p className="hrms-lms-form-guidance text-sm text-muted-foreground">Create a course that HR can assign by employee or role.</p>}<div className="space-y-1.5">
              <Label>Code</Label>
              <Input aria-label="Course code" value={courseForm.code} onChange={(e) => setCourseForm({ ...courseForm, code: e.target.value })} placeholder="POSH-101" />
            </div>
            <div className="hrms-lms-course-title space-y-1.5 sm:col-span-2">
              <Label>Title</Label>
              <Input aria-label="Course title" value={courseForm.title} onChange={(e) => setCourseForm({ ...courseForm, title: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Category</Label>
              <Input aria-label="Course category" value={courseForm.category} onChange={(e) => setCourseForm({ ...courseForm, category: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Delivery</Label>
              <NativeSelect className="h-10 w-full rounded-md border bg-background px-3 text-sm" aria-label="Course delivery" value={courseForm.delivery_mode} onChange={(e) => setCourseForm({ ...courseForm, delivery_mode: e.target.value })}>
                {["Online", "Classroom", "Blended", "External"].map((mode) => <option key={mode}>{mode}</option>)}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label>Hours</Label>
              <Input type="number" aria-label="Course hours" value={courseForm.duration_hours} onChange={(e) => setCourseForm({ ...courseForm, duration_hours: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Standard</Label>
              <NativeSelect className="h-10 w-full rounded-md border bg-background px-3 text-sm" aria-label="Course standard" value={courseForm.content_standard} onChange={(e) => setCourseForm({ ...courseForm, content_standard: e.target.value })}>
                {["Internal", "SCORM", "xAPI", "External"].map((standard) => <option key={standard}>{standard}</option>)}
              </NativeSelect>
            </div>
            <MobileDisclosure title="External learning details" maxWidth={480}><div className="space-y-1.5">
              <Label>External Launch URL</Label>
              <Input aria-label="External Launch URL" value={courseForm.external_launch_url} onChange={(e) => setCourseForm({ ...courseForm, external_launch_url: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>SCORM Version</Label>
              <Input aria-label="SCORM Version" value={courseForm.scorm_version} onChange={(e) => setCourseForm({ ...courseForm, scorm_version: e.target.value })} placeholder="1.2 / 2004" />
            </div>
            <div className="space-y-1.5">
              <Label>xAPI Activity ID</Label>
              <Input aria-label="xAPI Activity ID" value={courseForm.xapi_activity_id} onChange={(e) => setCourseForm({ ...courseForm, xapi_activity_id: e.target.value })} />
            </div>
            </MobileDisclosure>
            {phone && createCourse.isError && <p role="alert" className="hrms-lms-form-error text-sm text-destructive">Course could not publish. Your course details are retained.</p>}
            <div className="hrms-lms-form-actions flex gap-2 sm:col-span-3">
              <Button data-save-action={phone ? "" : undefined} disabled={!courseForm.code || !courseForm.title || createCourse.isPending} onClick={() => createCourse.mutate()}>
                Publish
              </Button>
              <Button variant="outline" onClick={() => setShowCourseForm(false)}>Cancel</Button>
            </div></div></SmartCreateSection>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Course Catalog</CardTitle>
            <CardDescription>Role-based and compliance learning content.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? <div className="h-24 rounded-lg bg-muted/40" /> : courses?.length ? <GroupedRecords scope="apps/hrms/pages/lms/LMSPage:records-1" items={(courses) || []} fields={standardRecordGroups((courses) || [])} gridClassName="space-y-3" renderItem={(course) => (
              <div key={course.id} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-[1fr_auto] sm:items-center">
                <div>
                  <p className="font-medium">{course.title}</p>
                  <p className="text-sm text-muted-foreground">{course.code} - {course.category || "General"} - {course.delivery_mode} - {course.content_standard || "Internal"}</p>
                  {course.external_launch_url && <p className="mt-1 text-xs text-muted-foreground">{course.external_launch_url}</p>}
                </div>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{course.duration_hours} hrs</span>
                  {course.scorm_version && <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800">SCORM {course.scorm_version}</span>}
                  {course.xapi_activity_id && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">xAPI</span>}
                  {course.is_mandatory && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">Mandatory</span>}
                </div>
              </div>
            )}/> : (!phone || coursesQuery.isSuccess) && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No courses published yet.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Learning Queue</CardTitle>
            <CardDescription>Recent assignments and certificate renewals.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {<GroupedRecords scope="apps/hrms/pages/lms/LMSPage:records-2" items={((assignments || []).slice(0, phone ? undefined : 5)) || []} fields={standardRecordGroups(((assignments || []).slice(0, phone ? undefined : 5)) || [])} gridClassName="space-y-3" renderItem={(item) => (
              <div key={item.id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">Employee #{item.employee_id}</p>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{item.status}</span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{courseTitleById.get(item.course_id) || `Course ${item.course_id}`}{item.due_date ? ` due ${item.due_date}` : ""}</p>
              </div>
            )}/>}
            {<GroupedRecords scope="apps/hrms/pages/lms/LMSPage:records-3" items={((certifications || []).slice(0, phone ? undefined : 4)) || []} fields={standardRecordGroups(((certifications || []).slice(0, phone ? undefined : 4)) || [])} gridClassName="space-y-3" renderItem={(cert) => (
              <div key={`cert-${cert.id}`} className="rounded-lg border p-3">
                <p className="text-sm font-medium">{cert.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">Employee #{cert.employee_id}{cert.expires_on ? ` expires ${cert.expires_on}` : ""}</p>
                {cert.renewal_required && <p className="mt-1 text-xs text-amber-700">Renewal {cert.renewal_status || "Due"}{cert.renewal_due_on ? ` by ${cert.renewal_due_on}` : ""}</p>}
              </div>
            )}/>}
            {<GroupedRecords scope="apps/hrms/pages/lms/LMSPage:records-4" items={((renewals || []).slice(0, phone ? undefined : 5)) || []} fields={standardRecordGroups(((renewals || []).slice(0, phone ? undefined : 5)) || [])} gridClassName="space-y-3" renderItem={(renewal) => (
              <div key={`renewal-${renewal.id}`} className="rounded-lg border p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">Certification #{renewal.certification_id}</p>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{renewal.status}</span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">Employee #{renewal.employee_id} due {renewal.due_on}</p>
              </div>
            )}/>}
            {phone && assignmentsQuery.isPending && <p role="status" className="text-sm text-muted-foreground">Loading learning queue…</p>}
            {phone && (certifications === undefined || renewals === undefined) && <p className="text-sm text-muted-foreground">Certification and renewal data is not loaded.</p>}
            {phone && assignmentsQuery.isSuccess && !assignments?.length && <p className="text-sm text-muted-foreground">No course assignments loaded.</p>}
            {(!phone || assignmentsQuery.isSuccess && certifications !== undefined && renewals !== undefined && !renewals.length) && !assignments?.length && !certifications?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No learning activity yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
