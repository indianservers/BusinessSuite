import {useMobile} from "@/components/mobile/useMobile";
import {MobileDisclosure} from "@/components/mobile/MobilePrimitives";
import "./probation-mobile.css";
import {SmartCreateSection} from "@/shared/creation/SmartCreateSection";
import CompactActions from "@/components/actions/CompactActions";
import { NativeSelect } from "@/components/ui/native-select";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCircle2, Download, FileText, RefreshCw, Send, TimerReset, UserX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { formatDate } from "@/lib/utils";
import { probationApi } from "@/services/api";

type ProbationEmployee = {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  managerName?: string;
  probationStartDate: string;
  probationEndDate: string;
  probationStatus: string;
  confirmationDate?: string;
  daysRemaining: number;
  latestReview?: {
    id: number;
    recommendation: string;
    status: string;
    performanceRating: number;
    conductRating: number;
    attendanceRating: number;
    comments?: string;
  };
  latestAction?: {
    actionType: string;
    effectiveDate: string;
    extendedUntil?: string;
    letterGenerated: boolean;
  };
};

const badgeTone = (status?: string) => {
  if (status === "confirmed") return "success";
  if (status === "terminated") return "destructive";
  if (status === "extended") return "warning";
  return "secondary";
};

export default function ProbationPage() {
  usePageTitle("Probation Management");
  const phone=useMobile(480),reviewFields=useRef<HTMLDivElement>(null);
  const [reviewSaved,setReviewSaved]=useState(0);
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [review, setReview] = useState({
    performanceRating: "3",
    conductRating: "3",
    attendanceRating: "3",
    recommendation: "confirm",
    comments: "",
  });
  const [action, setAction] = useState({ effectiveDate: "", extendedUntil: "", remarks: "" });

  const dashboard = useQuery({ queryKey: ["probation-dashboard"], queryFn: () => probationApi.dashboard().then((r) => r.data) });
  const dueList = useQuery({ queryKey: ["probation-due-list"], queryFn: () => probationApi.dueList({ days: 90 }).then((r) => r.data as ProbationEmployee[]) });

  const selected = useMemo(
    () => dueList.data?.find((employee) => employee.employeeId === selectedId) ?? dueList.data?.[0],
    [dueList.data, selectedId],
  );

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["probation-dashboard"] });
    qc.invalidateQueries({ queryKey: ["probation-due-list"] });
  };

  const submitReview = useMutation({
    mutationFn: () =>
      probationApi.review(selected!.employeeId, {
        performanceRating: Number(review.performanceRating),
        conductRating: Number(review.conductRating),
        attendanceRating: Number(review.attendanceRating),
        recommendation: review.recommendation,
        comments: review.comments || undefined,
      }),
    onSuccess: () => {
      toast({ title: "Probation review submitted" });
      if(phone)setReviewSaved(value=>value+1);
      refresh();
    },
    onError: () => toast({ title: "Could not submit review", variant: "destructive" }),
  });

  const processAction = useMutation({
    mutationFn: (type: "confirm" | "extend" | "terminate") => {
      const payload = {
        effectiveDate: action.effectiveDate || undefined,
        extendedUntil: action.extendedUntil || undefined,
        remarks: action.remarks || undefined,
      };
      if (type === "confirm") return probationApi.confirm(selected!.employeeId, payload);
      if (type === "extend") return probationApi.extend(selected!.employeeId, payload);
      return probationApi.terminate(selected!.employeeId, payload);
    },
    onSuccess: () => {
      toast({ title: "Probation action processed" });
      refresh();
    },
    onError: () => toast({ title: "Could not process action", variant: "destructive" }),
  });

  const runAlerts = useMutation({
    mutationFn: () => probationApi.runAlerts(),
    onSuccess: (response) => toast({ title: `${response.data.notificationsCreated} notification(s) created` }),
    onError: () => toast({ title: "Could not run alerts", variant: "destructive" }),
  });

  const downloadLetter = async () => {
    if (!selected) return;
    try {
      const response = await probationApi.letter(selected.employeeId);
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `probation-${selected.employeeCode}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      toast({ title: "No probation letter is available yet", variant: "destructive" });
    }
  };

  return (
    <div className="hrms-probation-page space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Employee lifecycle</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Probation management</h1>
          <p className="mt-1 text-sm text-muted-foreground">Track confirmation due dates, collect manager reviews, and issue confirmation or extension letters.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => runAlerts.mutate()} disabled={runAlerts.isPending}><Bell className="h-4 w-4" /> Run alerts</Button>
          <Button variant="outline" onClick={refresh}><RefreshCw className="h-4 w-4" /> Refresh</Button>
        </div>
      </div>

      <div className="hrms-probation-kpis grid gap-3 md:grid-cols-5">
        {[
          ["On probation", dashboard.data?.onProbation ?? (phone?"—":0)],
          ["Extended", dashboard.data?.extended ?? (phone?"—":0)],
          ["Due soon", dashboard.data?.dueSoon ?? (phone?"—":0)],
          ["Overdue", dashboard.data?.overdue ?? (phone?"—":0)],
          ["Pending reviews", dashboard.data?.pendingReviews ?? (phone?"—":0)],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="mt-1 text-2xl font-semibold">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {phone&&(dashboard.isError||dueList.isError)&&<p role="alert" className="text-sm text-destructive">Probation information could not load. <Button variant="outline" onClick={refresh} disabled={dashboard.isFetching||dueList.isFetching}>Retry probation</Button></p>}
      {phone&&dueList.isPending&&<p role="status">Loading probation employees…</p>}
      {phone&&selected&&<label className="hrms-probation-selector">Employee<NativeSelect aria-label="Probation employee" value={String(selected.employeeId)} onChange={e=>setSelectedId(Number(e.target.value))}>{dueList.data?.map(employee=><option key={employee.employeeId} value={employee.employeeId}>{employee.employeeName} · {employee.employeeCode}</option>)}</NativeSelect></label>}
      <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <MobileDisclosure title="Employees due for confirmation" maxWidth={480}><Card>
          <CardHeader>
            <CardTitle className="text-base">Due confirmation list</CardTitle>
            <CardDescription>{dueList.data?.length ?? 0} employee(s) due in the next 90 days.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {dueList.isLoading && <p className="rounded-lg border p-4 text-sm text-muted-foreground">Loading probation due list...</p>}
            {dueList.data?.map((employee) => (
              <button
                key={employee.employeeId}
                type="button"
                onClick={() => setSelectedId(employee.employeeId)}
                className={`w-full rounded-lg border p-4 text-left hover:bg-muted/40 ${selected?.employeeId === employee.employeeId ? "border-primary bg-primary/5" : ""}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{employee.employeeName}</p>
                    <p className="text-sm text-muted-foreground">
                      Ends {formatDate(employee.probationEndDate)} - {employee.daysRemaining} day(s)
                    </p>
                    <p className="text-xs text-muted-foreground">Manager: {employee.managerName || "Not assigned"}</p>
                  </div>
                  <Badge variant={badgeTone(employee.probationStatus) as any}>{employee.probationStatus.replace("_", " ")}</Badge>
                </div>
              </button>
            ))}
            {!dueList.isLoading && (!phone||!dueList.isError) && !dueList.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No probation confirmations due.</p>}
          </CardContent>
        </Card></MobileDisclosure>

        <div className="space-y-5">
          {selected ? (
            <>
              <Card>
                <CardHeader>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <CardTitle className="text-base">{selected.employeeName}</CardTitle>
                      <CardDescription>{selected.employeeCode} - Probation ends {formatDate(selected.probationEndDate)}</CardDescription>
                    </div>
                    <Badge variant={badgeTone(selected.probationStatus) as any}>{selected.probationStatus.replace("_", " ")}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Start</p><p className="font-medium">{formatDate(selected.probationStartDate)}</p></div>
                  <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">End</p><p className="font-medium">{formatDate(selected.probationEndDate)}</p></div>
                  <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Latest recommendation</p><p className="font-medium">{selected.latestReview?.recommendation || "Pending"}</p></div>
                </CardContent>
              </Card>

              <SmartCreateSection title="Submit probation review" mobileSheet={phone} completionRevision={phone?reviewSaved:0}><Card className="hrms-probation-review">
                <CardHeader>
                  <CardTitle className="text-base">Manager review</CardTitle>
                  <CardDescription>Managers can review direct reports; HR can submit on behalf when needed.</CardDescription>
                </CardHeader>
                <CardContent ref={reviewFields} className="space-y-3">
                  {phone&&<p className="text-sm font-medium">Reviewing {selected.employeeName} · {selected.employeeCode}. Managers can review direct reports; HR can submit on behalf when needed.</p>}
                  <div className="hrms-probation-ratings grid gap-3 md:grid-cols-4">
                    <div className="space-y-2"><Label>Performance</Label><Input aria-label="Performance" type="number" min="1" max="5" value={review.performanceRating} onChange={(event) => setReview({ ...review, performanceRating: event.target.value })} /></div>
                    <div className="space-y-2"><Label>Conduct</Label><Input aria-label="Conduct" type="number" min="1" max="5" value={review.conductRating} onChange={(event) => setReview({ ...review, conductRating: event.target.value })} /></div>
                    <div className="space-y-2"><Label>Attendance</Label><Input aria-label="Attendance" type="number" min="1" max="5" value={review.attendanceRating} onChange={(event) => setReview({ ...review, attendanceRating: event.target.value })} /></div>
                    <div className="space-y-2">
                      <Label>Recommendation</Label>
                      <NativeSelect aria-label="Review recommendation" value={review.recommendation} onChange={(event) => setReview({ ...review, recommendation: event.target.value })} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                        <option value="confirm">Confirm</option>
                        <option value="extend">Extend</option>
                        <option value="terminate">Terminate</option>
                      </NativeSelect>
                    </div>
                  </div>
                  <div className="space-y-2"><Label>Comments</Label><Input aria-label="Review comments" value={review.comments} onChange={(event) => setReview({ ...review, comments: event.target.value })} /></div>
                  {phone&&submitReview.isError&&<p role="alert" className="text-destructive">Could not submit review. Your ratings and comments are retained.</p>}
                  <Button data-save-action={phone?"":undefined} onClick={() => {if(phone){for(const input of reviewFields.current?.querySelectorAll<HTMLInputElement>('input[type="number"]')||[]){if(!input.reportValidity())return;}}submitReview.mutate();}} disabled={submitReview.isPending}><Send className="h-4 w-4" /> Submit review</Button>
                </CardContent>
              </Card></SmartCreateSection>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">HR action</CardTitle>
                  <CardDescription>Confirm, extend, or terminate probation and generate the appropriate letter.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="space-y-2"><Label>Effective date</Label><Input aria-label="Effective date" type="date" value={action.effectiveDate} onChange={(event) => setAction({ ...action, effectiveDate: event.target.value })} /></div>
                    <div className="space-y-2"><Label>Extended until</Label><Input aria-label="Extended until" type="date" value={action.extendedUntil} onChange={(event) => setAction({ ...action, extendedUntil: event.target.value })} /></div>
                    <div className="space-y-2"><Label>Remarks</Label><Input aria-label="Probation remarks" value={action.remarks} onChange={(event) => setAction({ ...action, remarks: event.target.value })} /></div>
                  </div>
                  {phone&&processAction.isError&&<p role="alert" className="text-destructive">Could not process action. Your dates and remarks are retained.</p>}
                  <CompactActions className="flex flex-wrap gap-2">
                    <Button onClick={() => processAction.mutate("confirm")} disabled={processAction.isPending}><CheckCircle2 className="h-4 w-4" /> Confirm</Button>
                    <Button variant="outline" onClick={() => processAction.mutate("extend")} disabled={processAction.isPending}><TimerReset className="h-4 w-4" /> Extend</Button>
                    <Button variant="destructive" onClick={() => processAction.mutate("terminate")} disabled={processAction.isPending}><UserX className="h-4 w-4" /> Terminate</Button>
                    <Button variant="outline" onClick={downloadLetter}><Download className="h-4 w-4" /> Download letter</Button>
                  </CompactActions>
                </CardContent>
              </Card>

              {selected.latestReview && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Latest review</CardTitle></CardHeader>
                  <CardContent className="rounded-lg border p-4 text-sm">
                    <p className="font-medium">{selected.latestReview.recommendation} - {selected.latestReview.status}</p>
                    <p className="text-muted-foreground">Performance {selected.latestReview.performanceRating}/5, Conduct {selected.latestReview.conductRating}/5, Attendance {selected.latestReview.attendanceRating}/5</p>
                    <p className="mt-2">{selected.latestReview.comments || "No comments"}</p>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card><CardContent className="p-6 text-sm text-muted-foreground"><FileText className="mb-3 h-5 w-5" />Select an employee to manage probation.</CardContent></Card>
          )}
        </div>
      </div>
    </div>
  );
}
