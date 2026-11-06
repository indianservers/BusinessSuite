import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { payrollApi } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { toast } from "@/hooks/use-toast";
import { formatCurrencyPrecise } from "@/lib/utils";
import { type DeliverySettings, payrollError } from "./PayrollDeliverySettings";

type Batch = { id: number; payroll_run_id: number; total_amount: number; status: string };
type PayoutState = { batch_id: number; status: string; approved_by?: number; total_amount: number; items: { id: number; record_id: number; mode: string; status: string; provider_id?: string; utr?: string; error?: string }[] };

export default function SalaryPayouts() {
  const qc = useQueryClient();
  const [runId, setRunId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [confirmTotal, setConfirmTotal] = useState("");
  const [connection, setConnection] = useState({ key_id: "", key_secret: "", debit_account: "", mode: "test" });
  const [connectionDirty, setConnectionDirty] = useState(false);
  const editConnection = (value: typeof connection) => { setConnectionDirty(true); setConnection(value); };
  const config = useQuery({ queryKey: ["payroll-delivery-settings"], queryFn: () => payrollApi.deliverySettings().then(r => r.data as DeliverySettings) });
  const runs = useQuery({ queryKey: ["payroll-runs"], queryFn: () => payrollApi.runs().then(r => r.data as { id: number; month: number; year: number; status: string }[]) });
  const batches = useQuery({ queryKey: ["salary-payout-batches", runId], queryFn: () => payrollApi.paymentBatches(runId ? { payroll_run_id: Number(runId) } : undefined).then(r => r.data as Batch[]) });
  const status = useQuery({ queryKey: ["salary-payout-status", batchId], queryFn: () => payrollApi.payoutStatus(Number(batchId)).then(r => r.data as PayoutState), enabled: Boolean(batchId) });
  useEffect(() => { if (config.data && !connectionDirty) setConnection(current => ({ ...current, key_id: config.data.payout.key_id || "", mode: config.data.payout.mode })); }, [config.data, connectionDirty]);
  const batch = batches.data?.find(item => item.id === Number(batchId));
  const refresh = () => { qc.invalidateQueries({ queryKey: ["salary-payout-batches"] }); qc.invalidateQueries({ queryKey: ["salary-payout-status"] }); setConfirmed(false); setConfirmTotal(""); };
  const mutation = useMutation({ mutationFn: async (action: string) => {
    if (action === "connection") return payrollApi.savePayoutConnection(connection);
    if (action === "create") return payrollApi.prepareDirectPayoutBatch(Number(runId));
    if (action === "approve") return payrollApi.approvePayouts(Number(batchId));
    if (action === "reconcile") return payrollApi.reconcilePayouts(Number(batchId));
    if (action.startsWith("retry:")) return payrollApi.preparePayoutRetry(Number(batchId), Number(action.split(":")[1]), { confirm_total: confirmTotal, confirm_mode: config.data?.payout.mode });
    return payrollApi.submitPayouts(Number(batchId), { confirm_total: confirmTotal, confirm_mode: config.data?.payout.mode });
  }, onSuccess: (response, action) => {
    toast({ title: action === "submit" ? "Payout request processed; review each provider status" : "Salary payout workflow updated" });
    if (action === "connection") { setConnection(current => ({ ...current, key_secret: "" })); qc.invalidateQueries({ queryKey: ["payroll-delivery-settings"] }); }
    if (action === "create") setBatchId(String(response.data.id));
    refresh();
  }, onError: error => toast({ title: "Salary payout operation failed", description: payrollError(error), variant: "destructive" }) });
  return <div className="space-y-5">
    <Card><CardHeader><CardTitle>Salary Payouts · RazorpayX</CardTitle></CardHeader><CardContent className="space-y-4">
      <p className="text-sm">Connect your company payout account, prepare and approve a finalized-payroll batch, then explicitly authorize its total. Test payouts never mark salaries as paid.</p>
      <p className="text-xs text-muted-foreground">Each submission sends up to five employee payouts. Submit again to continue a larger batch; saved provider requests are not duplicated. Refresh provider status to verify settlement.</p>
      <p className="text-sm font-medium">Connection: {config.data?.payout.configured ? `${config.data.payout.mode.toUpperCase()} · account ending ${config.data.payout.debit_account_last4}` : "Not configured"}</p>
      {config.data && !config.data.can_approve && <p className="text-sm">A payroll approver must configure the payout connection and authorize salary payments.</p>}
      {config.isError && <p role="alert">Payout connection could not load. <Button variant="outline" onClick={() => config.refetch()}>Retry connection</Button></p>}
      <details><summary className="cursor-pointer text-sm font-medium">Configure payout connection</summary><div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label>Provider mode<NativeSelect aria-label="Payout provider mode" className="h-10 w-full rounded border p-2" value={connection.mode} onChange={e => editConnection({ ...connection, mode: e.target.value })}><option value="test">Test</option><option value="live">Live</option></NativeSelect></label>
        <label>API key ID<Input aria-label="Payout API key ID" autoComplete="off" value={connection.key_id} onChange={e => editConnection({ ...connection, key_id: e.target.value })} /></label>
        <label>API secret<Input aria-label="Payout API secret" type="password" autoComplete="new-password" value={connection.key_secret} onChange={e => editConnection({ ...connection, key_secret: e.target.value })} placeholder="Leave blank to retain the current secret" /></label>
        <label>RazorpayX debit account<Input aria-label="Payout debit account" value={connection.debit_account} onChange={e => editConnection({ ...connection, debit_account: e.target.value })} /></label>
        <Button disabled={mutation.isPending || !config.data?.can_approve || !connection.debit_account || !connection.key_id} onClick={() => mutation.mutate("connection")}>Save payout connection</Button>
      </div></details>
    </CardContent></Card>
    <Card><CardHeader><CardTitle>Prepare &amp; Approve Salary Payments</CardTitle></CardHeader><CardContent className="space-y-4">
      <label>Finalized payroll run<NativeSelect aria-label="Salary payout payroll run" className="h-10 w-full rounded border p-2" value={runId} onChange={e => { setRunId(e.target.value); setBatchId(""); setConfirmed(false); }}><option value="">Select payroll run</option>{runs.data?.filter(run => ["locked", "paid"].includes(run.status.toLowerCase())).map(run => <option key={run.id} value={run.id}>{run.month}/{run.year} · {run.status} · Run #{run.id}</option>)}</NativeSelect></label>
      <Button variant="outline" disabled={!runId || mutation.isPending || !config.data?.can_manage} onClick={() => mutation.mutate("create")}>Prepare salary payment batch</Button>
      <label className="block">Payment batch<NativeSelect aria-label="Salary payment batch" className="h-10 w-full rounded border p-2" value={batchId} onChange={e => { setBatchId(e.target.value); setConfirmed(false); }}><option value="">Select batch</option>{batches.data?.map(item => <option key={item.id} value={item.id}>Batch #{item.id} · {formatCurrencyPrecise(Number(item.total_amount))} · {item.status}</option>)}</NativeSelect></label>
      {batch && <div className="space-y-3 rounded border p-4"><p className="font-medium">{formatCurrencyPrecise(Number(batch.total_amount))} · {status.data?.status || batch.status}</p>
        <div className="flex flex-wrap gap-2"><Button disabled={mutation.isPending || !config.data?.can_approve || batch.status !== "Generated"} onClick={() => mutation.mutate("approve")}>Approve payout batch</Button><Button variant="outline" disabled={mutation.isPending || !config.data?.can_approve} onClick={() => mutation.mutate("reconcile")}>Refresh provider status</Button></div>
        <label className="block">Confirm total amount<Input aria-label="Confirm salary payout total" inputMode="decimal" value={confirmTotal} onChange={e => setConfirmTotal(e.target.value)} /></label>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I authorize this {config.data?.payout.mode || "test"} payout batch for the displayed amount.</label>
        <Button disabled={mutation.isPending || !confirmed || Number(confirmTotal) !== Number(batch.total_amount) || !status.data?.approved_by || !config.data?.payout.configured} onClick={() => mutation.mutate("submit")}>{config.data?.payout.mode === "live" ? "Send live salary payouts" : "Send test salary payouts"}</Button>
      </div>}
      {(batches.isError || status.isError) && <p role="alert">Payment details could not load. <Button onClick={refresh}>Retry payment details</Button></p>}
      {status.data?.items.map(item => <div key={item.id} className="space-y-2 rounded border p-3 text-sm"><strong>Salary record #{item.record_id} · {item.mode} · {item.status}</strong><p>Provider: {item.provider_id || "Awaiting provider confirmation"} · UTR: {item.utr || "Pending"}</p>{item.error && <p role="alert">{item.error}</p>}{["failed", "reversed", "rejected", "cancelled"].includes(item.status.replace("test_", "")) && <Button size="sm" variant="outline" disabled={mutation.isPending || !config.data?.can_approve || !confirmed || Number(confirmTotal) !== Number(batch?.total_amount)} onClick={() => mutation.mutate(`retry:${item.id}`)}>Prepare corrected retry</Button>}</div>)}
    </CardContent></Card>
  </div>;
}
