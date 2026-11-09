import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import { AlertDialog, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog";
import "./fnf-settlement-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import {useSearchParams,Link} from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileText, IndianRupee, Plus, RefreshCw, Send, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { employeeApi, exitApi, fnfApi } from "@/services/api";
import { formatCurrency, formatDate } from "@/lib/utils";

type FnFComponent = {
  id?: number;
  component_type: "earning" | "deduction";
  name: string;
  amount: number;
  source_module?: string;
  is_manual_adjustment?: boolean;
  remarks?: string;
};

type FnFSettlement = {
  id: number;
  employeeId: number;
  employeeCode?: string;
  employeeName: string;
  exitId?: number;
  lastWorkingDate?: string;
  settlementStatus: "draft" | "pending_approval" | "approved" | "paid" | "rejected";
  unpaidSalary: number;
  leaveEncashment: number;
  gratuityAmount: number;
  noticeRecovery: number;
  loanRecovery: number;
  reimbursementPayable: number;
  bonusPayable: number;
  otherEarnings: number;
  otherDeductions: number;
  netPayable: number;
  remarks?: string;
  clearanceStatus?: { total: number; completed: number; status: string };
  components: FnFComponent[];
  timeline?: Array<{ label: string; completed: boolean; at?: string }>;
};

const statusTone: Record<string, "default" | "secondary" | "success" | "warning" | "destructive"> = {
  draft: "secondary",
  pending_approval: "warning",
  approved: "success",
  paid: "success",
  rejected: "destructive",
};

const emptyComponent: FnFComponent = {
  component_type: "earning",
  name: "",
  amount: 0,
  source_module: "manual",
  is_manual_adjustment: true,
  remarks: "",
};

export default function FnFSettlementPage() {
  usePageTitle("Full & Final Settlement");
  const qc = useQueryClient();
  const phone = useMobile(480);
  const [phoneSaved, setPhoneSaved] = useState<string | null>(null);
  const [pendingSelection, setPendingSelection] = useState<number | null>(null);
  const [contextParams]=useSearchParams();
  const [employeeId, setEmployeeId] = useState(contextParams.get("employee_id")||"");
  const [exitId, setExitId] = useState("");
  const [lastWorkingDate, setLastWorkingDate] = useState("");
  const [exitReason, setExitReason] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [components, setComponents] = useState<FnFComponent[]>([]);
  const [remarks, setRemarks] = useState("");

  const employees = useQuery({
    queryKey: ["fnf-employees"],
    queryFn: () => employeeApi.list({ per_page: 100 }).then((r) => r.data.items ?? r.data),
  });
  const exits = useQuery({ queryKey: ["fnf-exits"], queryFn: () => exitApi.records().then((r) => r.data) });
  const settlements = useQuery({
    queryKey: ["fnf-settlements",employeeId],
    queryFn: () => fnfApi.list(employeeId?{employee_id:Number(employeeId)}:undefined).then((r) => r.data as FnFSettlement[]),
  });

  const selected = useMemo(
    () => settlements.data?.find((item) => item.id === selectedId) ?? settlements.data?.[0],
    [settlements.data, selectedId],
  );

  useEffect(() => {
    if (selected) {
      setSelectedId(selected.id);
      setComponents(selected.components ?? []);
      setRemarks(selected.remarks ?? "");
      if (phone) setPhoneSaved(JSON.stringify({components: selected.components ?? [], remarks: selected.remarks ?? ""}));
    }
  }, [selected?.id]);

  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ["fnf-settlements"] });
    qc.invalidateQueries({ queryKey: ["fnf-exits"] });
  };

  const generate = useMutation({
    mutationFn: () =>
      fnfApi.generate({
        employee_id: Number(employeeId),
        exit_id: exitId ? Number(exitId) : undefined,
        last_working_date: lastWorkingDate,
        exit_reason: exitReason || undefined,
      }),
    onSuccess: (response) => {
      toast({ title: "Settlement generated" });
      setSelectedId(response.data.id);
      setEmployeeId("");
      setExitId("");
      setLastWorkingDate("");
      setExitReason("");
      refreshAll();
    },
    onError: () => toast({ title: "Could not generate settlement", variant: "destructive" }),
  });

  const save = useMutation({
    mutationFn: () =>
      fnfApi.update(selected!.id, {
        remarks,
        components: components.filter((component) => component.name.trim()),
      }),
    onSuccess: () => {
      toast({ title: "Settlement updated" });
      if (phone) setPhoneSaved(JSON.stringify({components, remarks}));
      refreshAll();
    },
    onError: () => toast({ title: "Could not update settlement", variant: "destructive" }),
  });

  const action = useMutation({
    mutationFn: async ({ type, id }: { type: "submit" | "approve" | "reject" | "paid"; id: number }) => {
      if (type === "submit") { await fnfApi.submit(id); return; }
      if (type === "approve") { await fnfApi.approve(id, { remarks }); return; }
      if (type === "reject") { await fnfApi.reject(id, { rejection_reason: remarks || "Rejected during finance review" }); return; }
      await fnfApi.markPaid(id, { remarks });
    },
    onSuccess: () => {
      toast({ title: "Settlement status updated" });
      refreshAll();
    },
    onError: () => toast({ title: "Could not update status", variant: "destructive" }),
  });

  const downloadPdf = async (id: number) => {
    try {
      const response = await fnfApi.pdf(id);
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `fnf-settlement-${id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({ title: "Could not download PDF", variant: "destructive" });
      if (phone) throw error;
    }
  };

  const pdfDownload = useMutation({mutationFn: (id: number) => downloadPdf(id)});
  const phoneBusy = phone && (generate.isPending || save.isPending || action.isPending || pdfDownload.isPending);
  const phoneDirty = phone && !!selected && (JSON.stringify({components, remarks}) !== (phoneSaved ?? JSON.stringify({components: selected.components ?? [], remarks: selected.remarks ?? ""})));
  function chooseSettlement(id: number) {
    if (phoneBusy || id === selected?.id) return;
    if (phoneDirty) { setPendingSelection(id); return; }
    setSelectedId(id);
  }
  const updateComponent = (index: number, patch: Partial<FnFComponent>) => {
    setComponents((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch, is_manual_adjustment: true } : item)));
  };

  const componentFields = (component: FnFComponent, index: number) => [
    {label: "Type", input: <NativeSelect disabled={phoneBusy} aria-label={phone ? `Type for component ${index + 1}` : undefined} value={component.component_type} onChange={event => updateComponent(index, {component_type: event.target.value as FnFComponent["component_type"]})} className="h-9 rounded-md border bg-background px-2"><option value="earning">Earning</option><option value="deduction">Deduction</option></NativeSelect>},
    {label: "Component", input: <Input disabled={phoneBusy} aria-label={phone ? `Name for component ${index + 1}` : undefined} value={component.name} onChange={event => updateComponent(index, {name: event.target.value})} />},
    {label: "Source", input: <Input disabled={phoneBusy} aria-label={phone ? `Source for component ${index + 1}` : undefined} value={component.source_module ?? ""} onChange={event => updateComponent(index, {source_module: event.target.value})} />},
    {label: "Amount", input: <Input disabled={phoneBusy} aria-label={phone ? `Amount for component ${index + 1}` : undefined} inputMode={phone ? "decimal" : undefined} type="number" min="0" step="0.01" value={component.amount} onChange={event => updateComponent(index, {amount: Number(event.target.value)})} />},
    {label: "Remarks", input: <Input disabled={phoneBusy} aria-label={phone ? `Remarks for component ${index + 1}` : undefined} value={component.remarks ?? ""} onChange={event => updateComponent(index, {remarks: event.target.value})} />},
  ];
  const totalEarnings = components.filter((item) => item.component_type === "earning").reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const totalDeductions = components.filter((item) => item.component_type === "deduction").reduce((sum, item) => sum + Number(item.amount || 0), 0);

  return (
    <div className="hrms-fnf space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Payroll exit</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Full & Final settlement</h1>
          <p className="mt-1 text-sm text-muted-foreground">Generate, review, approve, and pay employee exit settlements from real HRMS data.</p>
        </div>
        <Button disabled={phoneBusy} variant="outline" onClick={refreshAll}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-5">
          <SmartCreateSection title="Generate settlement" mobileSheet={phone} trigger={phone ? <Button className="w-full"><Plus className="h-4 w-4" />Generate settlement</Button> : undefined} size="large"><Card>
            <CardHeader>
              <CardTitle className="text-base">Generate settlement</CardTitle>
              <CardDescription>Pull salary, leave, loans, reimbursements, and clearance context.</CardDescription>
            </CardHeader>
            <CardContent className="hrms-fnf-create space-y-3">
              <div className="space-y-2">
                <Label htmlFor="fnf-employee">Employee</Label>
                <NativeSelect id="fnf-employee" disabled={phoneBusy} loading={employees.isFetching} error={employees.isError} value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select employee</option>
                  {employees.data?.map((employee: any) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.first_name} {employee.last_name} {employee.employee_id ? `(${employee.employee_id})` : ""}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label htmlFor="fnf-exit">Exit record</Label>
                <NativeSelect id="fnf-exit" disabled={phoneBusy} loading={exits.isFetching} error={exits.isError} value={exitId} onChange={(event) => setExitId(event.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Use employee's current exit or create one</option>
                  {exits.data
                    ?.filter((record: any) => !employeeId || Number(record.employee_id) === Number(employeeId))
                    .map((record: any) => (
                      <option key={record.id} value={record.id}>
                        Exit #{record.id} - LWD {formatDate(record.last_working_date)}
                      </option>
                    ))}
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label htmlFor="fnf-lwd">Last working date</Label>
                <Input id="fnf-lwd" disabled={phoneBusy} type="date" value={lastWorkingDate} onChange={(event) => setLastWorkingDate(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="fnf-reason">Exit reason</Label>
                <Input id="fnf-reason" disabled={phoneBusy} value={exitReason} onChange={(event) => setExitReason(event.target.value)} placeholder="Resignation, termination, retirement..." />
              </div>
              {phone && employees.isError && <p role="alert">Employees could not load. <Button variant="outline" onClick={() => void employees.refetch()}>Retry employees</Button></p>}
              {phone && exits.isError && <p role="alert">Exit records could not load. <Button variant="outline" onClick={() => void exits.refetch()}>Retry exit records</Button></p>}
              {phone && generate.isError && <p role="alert" className="text-sm text-destructive">Settlement generation failed. Your inputs are retained; retry Generate settlement.</p>}
              <Button data-save-action={phone || undefined} aria-busy={phone ? generate.isPending : undefined} onClick={() => generate.mutate()} disabled={!employeeId || !lastWorkingDate || generate.isPending || phoneBusy}>
                <Plus className="h-4 w-4" /> Generate settlement
              </Button>
            </CardContent>
          </Card></SmartCreateSection>

          <MobileDisclosure maxWidth={480} title={`Settlements · ${phone && !settlements.data ? "—" : settlements.data?.length ?? 0}`}><Card>
            <CardHeader>
              <CardTitle className="text-base">Settlements</CardTitle>
              <CardDescription>{phone && !settlements.data ? "—" : settlements.data?.length ?? 0} records</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {settlements.isLoading && <p className="rounded-lg border p-4 text-sm text-muted-foreground">Loading settlements...</p>}
              {settlements.isError && <p role={phone ? "alert" : undefined} className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">Could not load settlements.{phone && <Button variant="outline" onClick={() => void settlements.refetch()}>Retry settlements</Button>}</p>}
              {settlements.data?.map((settlement) => (
                <button
                  type="button"
                  key={settlement.id}
                  disabled={phoneBusy}
                  onClick={() => phone ? chooseSettlement(settlement.id) : setSelectedId(settlement.id)}
                  className={`w-full rounded-lg border p-4 text-left transition hover:bg-muted/40 ${selected?.id === settlement.id ? "border-primary bg-primary/5" : ""}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{settlement.employeeName}</p>
                      <p className="text-sm text-muted-foreground">LWD {formatDate(settlement.lastWorkingDate ?? null)} - {formatCurrency(settlement.netPayable)}</p>
                    </div>
                    <Badge variant={statusTone[settlement.settlementStatus] ?? "secondary"}>{settlement.settlementStatus.replace("_", " ")}</Badge>
                  </div>
                </button>
              ))}
              {!settlements.isLoading && !(phone && settlements.isError) && !settlements.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No F&F settlements have been generated yet.</p>}
            </CardContent>
          </Card></MobileDisclosure>
        </div>

        <div className="space-y-5">
          {selected ? (
            <>
              <Card>
                <CardHeader>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <CardTitle className="text-base">{selected.employeeName}</CardTitle>
                      <CardDescription>
                        {selected.employeeCode || `Employee #${selected.employeeId}`} - LWD {formatDate(selected.lastWorkingDate ?? null)}
                      </CardDescription>
                    </div>
                    <Badge variant={statusTone[selected.settlementStatus] ?? "secondary"}>{selected.settlementStatus.replace("_", " ")}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="hrms-fnf-summary grid gap-3 md:grid-cols-4">
                    <div className="rounded-lg border p-3">
                      <p className="text-xs text-muted-foreground">Earnings</p>
                      <p className="mt-1 font-semibold">{formatCurrency(totalEarnings)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs text-muted-foreground">Deductions</p>
                      <p className="mt-1 font-semibold">{formatCurrency(totalDeductions)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs text-muted-foreground">Net payable</p>
                      <p className="mt-1 font-semibold text-green-600">{formatCurrency(selected.netPayable)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs text-muted-foreground">Clearance</p>
                      <p className="mt-1 font-semibold">{selected.clearanceStatus?.completed ?? 0}/{selected.clearanceStatus?.total ?? 0}</p>
                    </div>
                  </div>

                  {phone && save.isError && <p role="alert">Settlement adjustments could not save. Your edits are retained.</p>}
                  {phone && action.isError && <p role="alert">Settlement status could not update. Retry its action.</p>}
                  {phone && pdfDownload.isError && <p role="alert">Settlement PDF could not download. Retry Download PDF.</p>}
                  {phoneBusy && <p role="status">Processing settlement…</p>}
                  <div className="flex flex-wrap gap-2">
                    {selected.settlementStatus === "draft" || selected.settlementStatus === "rejected" ? (
                      <>
                        <Button variant="outline" onClick={() => save.mutate()} disabled={save.isPending || phoneBusy}>
                          <FileText className="h-4 w-4" /> Save adjustments
                        </Button>
                        <Button onClick={() => action.mutate({ type: "submit", id: selected.id })} disabled={action.isPending || phoneBusy}>
                          <Send className="h-4 w-4" /> Submit
                        </Button>
                      </>
                    ) : null}
                    {selected.settlementStatus === "pending_approval" && (
                      <>
                        <Button onClick={() => action.mutate({ type: "approve", id: selected.id })} disabled={action.isPending || phoneBusy}>
                          <CheckCircle2 className="h-4 w-4" /> Approve
                        </Button>
                        <Button variant="destructive" onClick={() => action.mutate({ type: "reject", id: selected.id })} disabled={action.isPending || phoneBusy}>
                          <XCircle className="h-4 w-4" /> Reject
                        </Button>
                      </>
                    )}
                    {selected.settlementStatus === "approved" && (
                      <Button onClick={() => action.mutate({ type: "paid", id: selected.id })} disabled={action.isPending || phoneBusy}>
                        <IndianRupee className="h-4 w-4" /> Mark paid
                      </Button>
                    )}
                    {(selected.settlementStatus === "approved" || selected.settlementStatus === "paid") && (
                      <Button variant="outline" disabled={phoneBusy} onClick={() => phone ? pdfDownload.mutate(selected.id) : downloadPdf(selected.id)}>
                        <Download className="h-4 w-4" /> Download PDF
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Component calculation</CardTitle>
                  <CardDescription>Edit HR-reviewed values with adjustment remarks before submission.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {phone ? <div className="hrms-fnf-components">{components.map((component, index) => {const fields = componentFields(component, index);return <details key={`${component.id ?? "new"}-${index}`} open={index === 0 || !component.id}><summary>{component.name || `Adjustment ${index + 1}`} · {formatCurrency(component.amount)}</summary><div className="hrms-fnf-component-fields">{[0,3,1,2,4].map(i => <label key={fields[i].label}>{fields[i].label}{fields[i].input}</label>)}</div></details>;})}</div> : (
                  <div className="overflow-x-auto rounded-lg border">
                    <GridTable gridId="apps/hrms/pages/payroll/FnFSettlementPage:table-1" className="w-full min-w-[760px] text-sm">
                      <thead className="bg-muted/60 text-left">
                        <tr>
                          <th className="px-3 py-2">Type</th>
                          <th className="px-3 py-2">Component</th>
                          <th className="px-3 py-2">Source</th>
                          <th className="px-3 py-2">Amount</th>
                          <th className="px-3 py-2">Remarks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {components.map((component, index) => (
                          <tr {...recordPreviewProps(component)} key={`${component.id ?? "new"}-${index}`} className="border-t">
                            {componentFields(component, index).map(field => <td key={field.label} className="px-3 py-2">{field.input}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </GridTable>
                  </div>
                  )}
                  <Button disabled={phoneBusy} variant="outline" onClick={() => setComponents((current) => [...current, { ...emptyComponent }])}>
                    <Plus className="h-4 w-4" /> Add adjustment
                  </Button>
                  <div className="space-y-2">
                    <Label htmlFor="fnf-review">Review remarks</Label>
                    <Input id="fnf-review" disabled={phoneBusy} value={remarks} onChange={(event) => setRemarks(event.target.value)} placeholder="Adjustment reason, finance note, rejection reason..." />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Approval timeline</CardTitle>
                </CardHeader>
                <CardContent className="hrms-fnf-timeline grid gap-3 md:grid-cols-4">
                  {selected.timeline?.map((item) => (
                    <div key={item.label} className={`rounded-lg border p-3 ${item.completed ? "border-green-200 bg-green-50 text-green-900" : ""}`}>
                      <p className="font-medium">{item.label}</p>
                      <p className="text-xs text-muted-foreground">{item.at ? formatDate(item.at) : "Pending"}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="p-6 text-sm text-muted-foreground">Select or generate a settlement to review details.</CardContent>
            </Card>
          )}
        </div>
      </div>
      {phone && <AlertDialog open={pendingSelection !== null} onOpenChange={open => {if (!open) setPendingSelection(null);}}><AlertDialogContent><AlertDialogTitle>Discard settlement changes?</AlertDialogTitle><AlertDialogDescription>Your unsaved adjustments and review remarks will be replaced by the selected settlement.</AlertDialogDescription><AlertDialogCancel>Continue editing</AlertDialogCancel><AlertDialogAction onClick={() => {setSelectedId(pendingSelection);setPendingSelection(null);}}>Discard and switch</AlertDialogAction></AlertDialogContent></AlertDialog>}
    </div>
  );
}
