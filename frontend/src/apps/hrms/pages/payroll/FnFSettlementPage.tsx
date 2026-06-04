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
  const [employeeId, setEmployeeId] = useState("");
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
    queryKey: ["fnf-settlements"],
    queryFn: () => fnfApi.list().then((r) => r.data as FnFSettlement[]),
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
      refreshAll();
    },
    onError: () => toast({ title: "Could not update settlement", variant: "destructive" }),
  });

  const action = useMutation({
    mutationFn: ({ type, id }: { type: "submit" | "approve" | "reject" | "paid"; id: number }) => {
      if (type === "submit") return fnfApi.submit(id);
      if (type === "approve") return fnfApi.approve(id, { remarks });
      if (type === "reject") return fnfApi.reject(id, { rejection_reason: remarks || "Rejected during finance review" });
      return fnfApi.markPaid(id, { remarks });
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
    } catch {
      toast({ title: "Could not download PDF", variant: "destructive" });
    }
  };

  const updateComponent = (index: number, patch: Partial<FnFComponent>) => {
    setComponents((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch, is_manual_adjustment: true } : item)));
  };

  const totalEarnings = components.filter((item) => item.component_type === "earning").reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const totalDeductions = components.filter((item) => item.component_type === "deduction").reduce((sum, item) => sum + Number(item.amount || 0), 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Payroll exit</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Full & Final settlement</h1>
          <p className="mt-1 text-sm text-muted-foreground">Generate, review, approve, and pay employee exit settlements from real HRMS data.</p>
        </div>
        <Button variant="outline" onClick={refreshAll}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Generate settlement</CardTitle>
              <CardDescription>Pull salary, leave, loans, reimbursements, and clearance context.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Employee</Label>
                <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Select employee</option>
                  {employees.data?.map((employee: any) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.first_name} {employee.last_name} {employee.employee_id ? `(${employee.employee_id})` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Exit record</Label>
                <select value={exitId} onChange={(event) => setExitId(event.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  <option value="">Use employee's current exit or create one</option>
                  {exits.data
                    ?.filter((record: any) => !employeeId || Number(record.employee_id) === Number(employeeId))
                    .map((record: any) => (
                      <option key={record.id} value={record.id}>
                        Exit #{record.id} - LWD {formatDate(record.last_working_date)}
                      </option>
                    ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Last working date</Label>
                <Input type="date" value={lastWorkingDate} onChange={(event) => setLastWorkingDate(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Exit reason</Label>
                <Input value={exitReason} onChange={(event) => setExitReason(event.target.value)} placeholder="Resignation, termination, retirement..." />
              </div>
              <Button onClick={() => generate.mutate()} disabled={!employeeId || !lastWorkingDate || generate.isPending}>
                <Plus className="h-4 w-4" /> Generate settlement
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Settlements</CardTitle>
              <CardDescription>{settlements.data?.length ?? 0} records</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {settlements.isLoading && <p className="rounded-lg border p-4 text-sm text-muted-foreground">Loading settlements...</p>}
              {settlements.isError && <p className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">Could not load settlements.</p>}
              {settlements.data?.map((settlement) => (
                <button
                  type="button"
                  key={settlement.id}
                  onClick={() => setSelectedId(settlement.id)}
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
              {!settlements.isLoading && !settlements.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No F&F settlements have been generated yet.</p>}
            </CardContent>
          </Card>
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
                  <div className="grid gap-3 md:grid-cols-4">
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

                  <div className="flex flex-wrap gap-2">
                    {selected.settlementStatus === "draft" || selected.settlementStatus === "rejected" ? (
                      <>
                        <Button variant="outline" onClick={() => save.mutate()} disabled={save.isPending}>
                          <FileText className="h-4 w-4" /> Save adjustments
                        </Button>
                        <Button onClick={() => action.mutate({ type: "submit", id: selected.id })} disabled={action.isPending}>
                          <Send className="h-4 w-4" /> Submit
                        </Button>
                      </>
                    ) : null}
                    {selected.settlementStatus === "pending_approval" && (
                      <>
                        <Button onClick={() => action.mutate({ type: "approve", id: selected.id })} disabled={action.isPending}>
                          <CheckCircle2 className="h-4 w-4" /> Approve
                        </Button>
                        <Button variant="destructive" onClick={() => action.mutate({ type: "reject", id: selected.id })} disabled={action.isPending}>
                          <XCircle className="h-4 w-4" /> Reject
                        </Button>
                      </>
                    )}
                    {selected.settlementStatus === "approved" && (
                      <Button onClick={() => action.mutate({ type: "paid", id: selected.id })} disabled={action.isPending}>
                        <IndianRupee className="h-4 w-4" /> Mark paid
                      </Button>
                    )}
                    {(selected.settlementStatus === "approved" || selected.settlementStatus === "paid") && (
                      <Button variant="outline" onClick={() => downloadPdf(selected.id)}>
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
                  <div className="overflow-x-auto rounded-lg border">
                    <table className="w-full min-w-[760px] text-sm">
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
                          <tr key={`${component.id ?? "new"}-${index}`} className="border-t">
                            <td className="px-3 py-2">
                              <select value={component.component_type} onChange={(event) => updateComponent(index, { component_type: event.target.value as FnFComponent["component_type"] })} className="h-9 rounded-md border bg-background px-2">
                                <option value="earning">Earning</option>
                                <option value="deduction">Deduction</option>
                              </select>
                            </td>
                            <td className="px-3 py-2"><Input value={component.name} onChange={(event) => updateComponent(index, { name: event.target.value })} /></td>
                            <td className="px-3 py-2"><Input value={component.source_module ?? ""} onChange={(event) => updateComponent(index, { source_module: event.target.value })} /></td>
                            <td className="px-3 py-2"><Input type="number" min="0" step="0.01" value={component.amount} onChange={(event) => updateComponent(index, { amount: Number(event.target.value) })} /></td>
                            <td className="px-3 py-2"><Input value={component.remarks ?? ""} onChange={(event) => updateComponent(index, { remarks: event.target.value })} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Button variant="outline" onClick={() => setComponents((current) => [...current, { ...emptyComponent }])}>
                    <Plus className="h-4 w-4" /> Add adjustment
                  </Button>
                  <div className="space-y-2">
                    <Label>Review remarks</Label>
                    <Input value={remarks} onChange={(event) => setRemarks(event.target.value)} placeholder="Adjustment reason, finance note, rejection reason..." />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Approval timeline</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-4">
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
    </div>
  );
}
