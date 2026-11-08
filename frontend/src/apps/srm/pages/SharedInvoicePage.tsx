import {useModuleAction} from "@/hooks/use-module-action";
import { PaymentRequestButton } from "@/shared/payments/PaymentRequests";
import MobilePdfActions from "@/components/mobile/MobilePdfActions";
import CompactForm from "@/components/forms/CompactForm";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { InvoicePaymentForm } from "./ConnectedCollectionsPage";
import { useAuthStore } from "@/store/authStore";
import {lazy, Suspense, useState} from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CommercialIdentityForm } from "@/apps/project-management/pages/ProjectBillingPage";

const RecordTemplatePicker=lazy(()=>import('@/shared/template-design/RecordTemplatePicker'));

export default function SharedInvoicePage() {
  const { id } = useParams();
  const uid = useAuthStore((state) => state.user?.id);
  return <InvoiceWorkspace key={`${uid}-${id}`} id={id} />;
}

function InvoiceWorkspace({ id }: { id?: string }) {
  const allowCreate=useModuleAction("create"),allowEdit=useModuleAction("edit"),allowApprove=useModuleAction("approve"),allowExport=useModuleAction("export");
  const uid = useAuthStore((state) => state.user?.id);
  const [notice, setNotice] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const query = useQuery({
    queryKey: ["shared-invoice", uid, id],
    queryFn: async () => (await api.get(`/srm/business/invoices/${id}`)).data,
    refetchInterval: 10000,
  });
  const action = useMutation({
    mutationFn: async (name: string) =>
      (await api.post(`/srm/invoices/${id}/${name}`)).data,
    onSuccess: async (data) => {
      setNotice(
        data.delivery
          ? `Delivery: ${data.delivery.status}. ${data.delivery.error || ""}`
          : "Invoice issued.",
      );
      await query.refetch();
    },
  });
  const pdf = useMutation({
    mutationFn: async () =>
      (await api.get(`/srm/invoices/${id}/pdf`, { responseType: "blob" })).data,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${query.data.invoice_number}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    },
  });
  const cancel = useMutation({
    mutationFn: () =>
      api.post(`/srm/business/invoices/${id}/cancel`, { reason: cancelReason }),
    onSuccess: async () => {
      setNotice(
        "Invoice cancelled. Source reservations remain held for finance review.",
      );
      await query.refetch();
    },
  });
  if (query.isPending) return <p>Loading invoice…</p>;
  if (query.isError)
    return (
      <p role="alert">
        Invoice unavailable or you do not have financial access.{" "}
        <Button onClick={() => query.refetch()}>Retry</Button>
      </p>
    );
  const r = query.data;
  return (
    <div className="space-y-5">
      <Link to="/srm/invoices">← Sales invoices</Link>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="page-title">{r.invoice_number}</h1><Suspense fallback={null}><RecordTemplatePicker entity="invoice" recordId={Number(id)} source="srm"/></Suspense></div>
      {r.customer_id && <Button variant="outline" asChild><Link to={`/srm/customers/${r.customer_id}/360`}>Open customer 360</Link></Button>}
      {r.project_id && (
        <Link
          className="text-primary underline"
          to={`/pms/projects/${r.project_id}/billing`}
        >
          Open originating project
        </Link>
      )}
      <div className="mobile-only-panel"><ol className="mobile-timeline" aria-label="Invoice progress">{[["Document",r.document_status],["Delivery",r.delivery_status],["Payment",r.payment_status]].map(([label,status])=><li key={label}><strong>{label}</strong><small>{String(status||"Not available").replace(/_/g,' ')}</small></li>)}</ol><MobilePdfActions url={`/srm/invoices/${id}/pdf`} filename={`${r.invoice_number}.pdf`}/></div>
      <Card>
        <CardContent className="flex flex-wrap gap-6 p-5">
          <p>Document: {r.document_status}</p>
          <p>Delivery: {r.delivery_status}</p>
          <p>Payment: {r.payment_status}</p>
          <p>
            Total: {r.currency} {r.total_amount}
          </p>
          <p>Paid: {r.paid_amount}</p>
          <p>Outstanding: {r.balance_amount}</p>
        </CardContent>
      </Card>
      {r.document_status === "draft" && r.can_edit && allowEdit && (
        <Card>
          <CardHeader>
            <CardTitle>Customer and seller</CardTitle>
          </CardHeader>
          <CardContent>
            <CommercialIdentityForm
              initial={{
                customer_id: r.customer_id || "",
                seller_id: r.context?.seller_id || "",
                contact_id: r.context?.contact_id || "",
                currency: r.currency,
              }}
              onSave={async (value) => {
                await api.put(`/srm/business/invoices/${id}/context`, value);
                await query.refetch();
              }}
            />
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Invoice lines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {r.lines.map((l: any) => (
            <div className="border-b py-2" key={l.id}>
              <div className="flex flex-wrap justify-between gap-3">
                <div><RichTextContent legacyFormat="plain" value={l.description}/></div>
                <span>
                  {l.quantity} × {l.unit_price}
                </span>
                <span>
                  Discount {l.discount_amount || 0}; tax {l.tax_amount}
                </span>
                <strong>{l.line_total}</strong>
              </div>
              {r.document_status === "draft" &&
                r.can_edit && allowEdit &&
                [null, "manual", "external_adjustment"].includes(
                  l.source_type,
                ) && (
                  <DraftLineEditor
                    key={`${l.id}-${l.line_total}`}
                    invoiceId={Number(id)}
                    line={l}
                    onSave={() => query.refetch()}
                  />
                )}
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={!allowExport||pdf.isPending}
              onClick={() => pdf.mutate()}
            >
              Preview / download PDF
            </Button>
            {r.document_status === "draft" && r.can_issue && allowApprove && (
              <Button
                disabled={action.isPending}
                onClick={() => action.mutate("approve")}
              >
                Issue invoice
              </Button>
            )}
            {r.document_status === "issued" && r.can_edit && allowCreate && (
              <Button
                disabled={
                  action.isPending ||
                  ["sent", "sending", "unknown"].includes(r.delivery_status)
                }
                onClick={() => action.mutate("send")}
              >
                {["blocked", "failed"].includes(r.delivery_status)
                  ? "Retry delivery"
                  : "Send to billing recipient"}
              </Button>
            )}
          </div>
          {notice && <p role="status">{notice}</p>}
          {(action.isError || pdf.isError) && (
            <p role="alert">
              {(action.error as any)?.response?.data?.detail ||
                "Unable to complete this action. Please retry."}
            </p>
          )}
          {r.context?.customer_snapshot && (
            <p>
              Billed to: {r.context.customer_snapshot.name} —{" "}
              {r.context.customer_snapshot.address}
            </p>
          )}
        </CardContent>
      </Card>
      {r.can_record_payment && allowApprove && <PaymentRequestButton source="srm_invoice" sourceId={Number(id)}/>}
      {r.can_record_payment && (allowApprove||allowEdit) &&
        r.document_status === "issued" &&
        Number(r.balance_amount) > 0 && (
          <InvoicePaymentForm invoice={r} onSaved={() => query.refetch()} />
        )}
      <Card>
        <CardHeader>
          <CardTitle>History and delivery attempts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {r.history.map((h: any) => (
            <p key={`h${h.id}`}>
              {h.created_at} — {h.to_status} — {h.notes}
            </p>
          ))}
          {r.deliveries.map((d: any) => (
            <p key={`d${d.id}`}>
              {d.created_at} — {d.status} — {d.error} — Reference {d.request_id}
            </p>
          ))}
          {r.payments.map((p: any) => (
            <p key={`p${p.id}`}>
              Payment {p.amount} — Receipt #{p.receipt_id} — {p.allocated_at}
              {p.reversed_at ? ` — Reversed ${p.reversed_at}` : ""}
            </p>
          ))}
        </CardContent>
      </Card>
      {r.can_issue && allowCreate && r.document_status !== "cancelled" && (
        <details className="rounded-lg border p-4">
          <summary>Finance adjustments</summary>
          <p className="my-3 text-sm text-muted-foreground">
            Reverse applied payments and posted vouchers through Accounting
            before cancellation. Source reservations stay held for finance
            review.
          </p>
          <Link className="text-primary underline" to="/fam/vouchers">
            Open Accounting vouchers
          </Link>
          <CompactForm
            className="mt-4 flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              cancel.mutate();
            }}
          >
            <label className="text-sm">
              Cancellation reason
              <input
                className="mt-1 block h-10 rounded-md border bg-background px-3"
                required
                minLength={3}
                maxLength={500}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            </label>
            <Button
              variant="destructive"
              type="submit"
              disabled={cancel.isPending}
            >
              Cancel invoice
            </Button>
            {cancel.isError && (
              <p role="alert">
                {(cancel.error as any)?.response?.data?.detail ||
                  "Unable to cancel this invoice"}
              </p>
            )}
          </CompactForm>
        </details>
      )}
    </div>
  );
}

function DraftLineEditor({
  invoiceId,
  line,
  onSave,
}: {
  invoiceId: number;
  line: any;
  onSave: () => unknown;
}) {
  const save = useMutation({
    mutationFn: (data: Record<string, FormDataEntryValue>) =>
      api.patch(`/srm/business/invoices/${invoiceId}/lines/${line.id}`, data),
    onSuccess: () => onSave(),
  });
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-primary">Edit draft line</summary>
      <CompactForm
        className="mt-2 grid gap-2 sm:grid-cols-6"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(Object.fromEntries(new FormData(event.currentTarget)));
        }}
      >
        {[
          "description",
          "quantity",
          "unit_price",
          "discount_amount",
          "tax_amount",
        ].map((key) => (
          <label className="text-sm" key={key}>
            {key.replace(/_/g, " ")}
            <input
              className="h-10 w-full rounded-md border bg-background px-2"
              name={key}
              required
              type={key === "description" ? "text" : "number"}
              min="0"
              step="any"
              defaultValue={line[key]}
            />
          </label>
        ))}
        <Button className="self-end" disabled={save.isPending} type="submit">
          Save line
        </Button>
        {save.isError && (
          <p role="alert">
            {(save.error as any)?.response?.data?.detail ||
              "Line could not be saved"}
          </p>
        )}
      </CompactForm>
    </details>
  );
}
