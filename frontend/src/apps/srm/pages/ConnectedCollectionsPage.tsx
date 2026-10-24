import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { InvoiceList } from "@/apps/project-management/pages/ProjectBillingPage";

type Row = Record<string, any>;
export function InvoicePaymentForm({
  invoice,
  onSaved,
}: {
  invoice: Row;
  onSaved?: () => unknown;
}) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [receipt, setReceipt] = useState<number | null>(null);
  const save = useMutation({
    mutationFn: () =>
      api.post(`/srm/business/invoices/${invoice.id}/payments`, {
        request_id: requestId,
        amount,
        reference,
      }),
    onSuccess: (response) => {
      setReceipt(response.data.receipt_id);
      setAmount("");
      setReference("");
      setRequestId(crypto.randomUUID());
      onSaved?.();
      for (const key of [
        "collection-invoices",
        "project-billing",
        "shared-invoice",
        "customer-commercial-history",
        "srm",
      ])
        queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <details className="w-full">
      <summary>Record payment</summary>
      <p className="my-2 text-sm text-muted-foreground">
        Customer #{invoice.customer_id} · {invoice.currency} · Outstanding{" "}
        {invoice.balance_amount}. The receipt uses this invoice's seller and
        currency.
      </p>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div>
          <Label htmlFor={`payment-amount-${invoice.id}`}>
            Amount received
          </Label>
          <Input
            id={`payment-amount-${invoice.id}`}
            required
            type="number"
            min="0.01"
            max={invoice.balance_amount}
            step="0.01"
            disabled={save.isPending}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`payment-reference-${invoice.id}`}>
            Bank / payment reference
          </Label>
          <Input
            id={`payment-reference-${invoice.id}`}
            maxLength={120}
            disabled={save.isPending}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={save.isPending || !amount}>
          Record received payment
        </Button>
      </form>
      {save.isError && (
        <p role="alert">
          {(save.error as any)?.response?.data?.detail ||
            "Unable to record payment. Your entries are preserved for retry."}
        </p>
      )}
      {receipt && (
        <p role="status">
          Receipt #{receipt} saved and applied to this invoice.
        </p>
      )}
    </details>
  );
}

export default function ConnectedCollectionsPage() {
  const uid = useAuthStore((state) => state.user?.id);
  const query = useQuery({
    queryKey: ["collection-invoices", uid],
    queryFn: async () =>
      (await api.get("/srm/business/collection-invoices")).data,
    refetchInterval: 10000,
  });
  if (query.isPending) return <p>Loading collections…</p>;
  if (query.isError)
    return (
      <p role="alert">
        Collections are unavailable or outside your financial permissions.{" "}
        <Button onClick={() => query.refetch()}>Retry</Button>
      </p>
    );
  return (
    <div className="space-y-5">
      <h1 className="page-title">Collections</h1>
      <p className="text-muted-foreground">
        Record actual customer payments against issued invoices. Project billing
        and customer history use these same receipt records.
      </p>
      <Card>
        <CardHeader>
          <CardTitle>Invoices and outstanding balances</CardTitle>
        </CardHeader>
        <CardContent>
          <InvoiceList
            invoices={query.data.items}
            actions={(row) =>
              query.data.can_record &&
              row.document_status === "issued" &&
              Number(row.balance_amount) > 0 ? (
                <InvoicePaymentForm
                  key={`${uid}-${row.id}`}
                  invoice={row}
                  onSaved={() => query.refetch()}
                />
              ) : null
            }
          />
        </CardContent>
      </Card>
    </div>
  );
}
