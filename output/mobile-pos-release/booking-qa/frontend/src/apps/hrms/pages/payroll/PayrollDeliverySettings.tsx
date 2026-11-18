import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { payrollApi } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";

export type PayslipTemplate = {
  layout: string; show_employee_code: boolean; show_working_days: boolean; show_ytd: boolean;
  show_employer_contributions: boolean; show_reimbursements: boolean; show_department: boolean; footer: string;
};
export type DeliverySettings = {
  can_manage: boolean; can_approve: boolean;
  ytd_basis: string; fy_start_month: number; regular_template: PayslipTemplate; settlement_template: PayslipTemplate;
  logo_available: boolean; signature_available: boolean; form16_trust_configured: boolean;
  payout: { provider: string; configured: boolean; key_id: string; mode: string; debit_account_last4: string };
};

export function payrollError(error: unknown) {
  const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
  return typeof detail === "string" ? detail : "The operation could not be completed. Please retry.";
}

export function downloadPayrollBlob(data: Blob, name: string) {
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url; link.download = name; document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function PayrollDeliverySettings() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["payroll-delivery-settings"], queryFn: () => payrollApi.deliverySettings().then(r => r.data as DeliverySettings) });
  const [form, setForm] = useState<DeliverySettings>();
  const [kind, setKind] = useState<"regular" | "settlement">("regular");
  useEffect(() => { if (query.data) setForm(current => current ? { ...current, logo_available: query.data.logo_available, signature_available: query.data.signature_available, can_manage: query.data.can_manage, can_approve: query.data.can_approve } : query.data); }, [query.data]);
  const onError = (error: unknown) => toast({ title: "Payroll settings could not be updated", description: payrollError(error), variant: "destructive" });
  const save = useMutation({ mutationFn: () => payrollApi.saveDeliverySettings(form), onSuccess: () => { toast({ title: "Payslip templates and year settings saved" }); qc.invalidateQueries({ queryKey: ["payroll-delivery-settings"] }); }, onError });
  const upload = useMutation({ mutationFn: ({ type, file }: { type: "logo" | "signature"; file: File }) => { const data = new FormData(); data.append("file", file); return payrollApi.uploadPayslipBranding(type, data); }, onSuccess: () => { toast({ title: "Payslip branding uploaded" }); qc.invalidateQueries({ queryKey: ["payroll-delivery-settings"] }); }, onError });
  const preview = useMutation({ mutationFn: () => payrollApi.previewPayslipTemplate(kind), onSuccess: r => downloadPayrollBlob(r.data, `${kind}-payslip-preview.pdf`), onError });
  if (query.isLoading) return <p>Loading payslip settings…</p>;
  if (query.isError || !form) return <div role="alert">Payslip settings could not load.<Button onClick={() => query.refetch()}>Retry settings</Button></div>;
  const templateKey = kind === "regular" ? "regular_template" : "settlement_template";
  const template = form[templateKey];
  const setTemplate = (values: Partial<PayslipTemplate>) => setForm({ ...form, [templateKey]: { ...template, ...values } });
  return <div className="space-y-5">
    <Card><CardHeader><CardTitle>Financial Year &amp; Payslip Templates</CardTitle></CardHeader><CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">Configure the year used for payslip totals and the regular and final-settlement PDF layouts for this company.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-sm">Payslip YTD basis<NativeSelect aria-label="Payslip YTD basis" className="h-10 w-full rounded border p-2" value={form.ytd_basis} onChange={e => setForm({ ...form, ytd_basis: e.target.value })}><option value="financial">Financial year</option><option value="calendar">Calendar year</option></NativeSelect></label>
        <label className="space-y-2 text-sm">Financial year starts<NativeSelect aria-label="Financial year starts" disabled={form.ytd_basis === "calendar"} className="h-10 w-full rounded border p-2" value={form.fy_start_month} onChange={e => setForm({ ...form, fy_start_month: Number(e.target.value) })}>{Array.from({ length: 12 }, (_, i) => <option key={i} value={i + 1}>{new Date(2026, i, 1).toLocaleString("en", { month: "long" })}</option>)}</NativeSelect></label>
      </div>
      <p className="text-xs text-muted-foreground">India tax forms continue to use April–March. These settings control payslip presentation and YTD aggregation. Previously generated PDFs are retained until HR regenerates them.</p>
    </CardContent></Card>
    <Card><CardHeader><CardTitle>Payslip Appearance</CardTitle></CardHeader><CardContent className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-sm">Document type<NativeSelect aria-label="Payslip document type" className="h-10 w-full rounded border p-2" value={kind} onChange={e => setKind(e.target.value as typeof kind)}><option value="regular">Regular payslip</option><option value="settlement">Full &amp; final settlement</option></NativeSelect></label>
        <label className="space-y-2 text-sm">Layout<NativeSelect aria-label="Payslip layout" className="h-10 w-full rounded border p-2" value={template.layout} onChange={e => setTemplate({ layout: e.target.value })}>{["standard", "compact", "professional"].map(value => <option key={value} value={value}>{value}</option>)}</NativeSelect></label>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">{([ ["show_employee_code", "Employee code"], ["show_department", "Department"], ["show_working_days", "Working and paid days"], ["show_ytd", "Year-to-date totals"], ["show_employer_contributions", "Employer contributions"], ["show_reimbursements", "Reimbursements"] ] as const).map(([key, label]) => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={template[key]} onChange={e => setTemplate({ [key]: e.target.checked })} />{label}</label>)}</div>
      <label className="block space-y-2 text-sm">Payslip footer<Input aria-label="Payslip footer" maxLength={300} value={template.footer} onChange={e => setTemplate({ footer: e.target.value })} /></label>
      <div className="grid gap-4 sm:grid-cols-2">{(["logo", "signature"] as const).map(type => <label key={type} className="space-y-2 text-sm">{type === "logo" ? "Company logo" : "Authorized signature image"} · {form[`${type}_available`] ? "uploaded" : "not uploaded"}<Input aria-label={`Upload payslip ${type}`} type="file" accept="image/png,image/jpeg" disabled={upload.isPending} onChange={e => { const file = e.target.files?.[0]; if (file) upload.mutate({ type, file }); e.target.value = ""; }} /></label>)}</div>
      <p className="text-xs text-muted-foreground">A signature image is visual branding. Form 16 digital signatures are verified separately in Statutory Compliance.</p>
      {!form.can_manage && <p className="text-sm">Payroll processing permission is required to change these settings.</p>}
      <div className="flex flex-wrap gap-2"><Button disabled={save.isPending || !form.can_manage} onClick={() => save.mutate()}>Save payslip settings</Button><Button variant="outline" disabled={preview.isPending} onClick={() => preview.mutate()}>Preview saved template</Button></div>
    </CardContent></Card>
  </div>;
}
