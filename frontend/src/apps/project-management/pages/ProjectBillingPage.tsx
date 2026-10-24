import { useAuthStore } from "@/store/authStore";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Row = Record<string, any>;
const read = async (path: string) => (await api.get(path)).data;
const errorText = (error: any) =>
  error?.response?.data?.detail || error?.message || "Please try again";

export function SharedCustomerSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const uid = useAuthStore((state) => state.user?.id);
  const [after, setAfter] = useState(0);
  const [search, setSearch] = useState("");
  const result = useQuery({
    queryKey: ["shared-customers", uid, search, after],
    queryFn: () =>
      read(
        `/srm/business/customers?q=${encodeURIComponent(search)}&after=${after}`,
      ),
  });
  const selected = useQuery({
    queryKey: ["shared-customer", uid, value],
    queryFn: () => read(`/srm/business/customers/${value}`),
    enabled: !!value,
  });
  return (
    <div className="space-y-2">
      <Input
        aria-label="Search shared customers"
        placeholder="Search customers"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setAfter(0);
        }}
      />
      <select
        className="h-10 w-full rounded-md border bg-background px-3"
        aria-label="Shared customer"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Select a shared customer</option>
        {selected.data &&
          !(result.data?.items || []).some(
            (r: Row) => String(r.id) === value,
          ) && <option value={value}>{selected.data.name}</option>}
        {(result.data?.items || []).map((r: Row) => (
          <option key={r.id} value={r.id}>
            {r.name}
          </option>
        ))}
      </select>
      {result.data?.next && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setAfter(result.data.next)}
        >
          More customers
        </Button>
      )}
      {after > 0 && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setAfter(0)}
        >
          First page
        </Button>
      )}
      {result.isError && <p role="alert">{errorText(result.error)}</p>}
    </div>
  );
}

export function CommercialIdentityForm({
  initial,
  onSave,
  showSources = false,
}: {
  initial?: Row;
  onSave: (value: Row) => Promise<unknown>;
  showSources?: boolean;
}) {
  const uid = useAuthStore((state) => state.user?.id);
  const [form, setForm] = useState<Row>(
    initial || {
      customer_id: "",
      seller_id: "",
      contact_id: "",
      team_id: "",
      currency: "INR",
    },
  );
  const sellers = useQuery({
    queryKey: ["shared-sellers", uid],
    queryFn: () => read("/srm/business/sellers"),
  });
  const teams = useQuery({
    queryKey: ["shared-teams", uid],
    queryFn: () => read("/srm/business/teams"),
  });
  const contacts = useQuery({
    queryKey: ["shared-contacts", uid, form.customer_id],
    queryFn: () => read(`/srm/business/customers/${form.customer_id}/contacts`),
    enabled: !!form.customer_id,
  });
  const orders = useQuery({
    queryKey: ["billing-commercial-orders", uid],
    queryFn: () => read("/srm/sales-orders"),
    enabled: showSources,
  });
  const engagements = useQuery({
    queryKey: ["billing-commercial-engagements", uid],
    queryFn: () => read("/srm/engagements"),
    enabled: showSources,
  });
  const save = useMutation({
    mutationFn: () =>
      onSave({
        customer_id: Number(form.customer_id),
        seller_id: Number(form.seller_id),
        contact_id: Number(form.contact_id) || null,
        team_id: Number(form.team_id) || null,
        currency: form.currency,
        ...(showSources
          ? {
              sales_order_id: Number(form.sales_order_id) || null,
              engagement_id: Number(form.engagement_id) || null,
            }
          : {}),
      }),
  });
  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div>
        <Label>Customer</Label>
        <SharedCustomerSelect
          value={String(form.customer_id || "")}
          onChange={(v) => setForm({ ...form, customer_id: v, contact_id: "" })}
        />
      </div>
      <div>
        <Label htmlFor="billing-seller">Seller legal entity</Label>
        <select
          id="billing-seller"
          required
          className="h-10 w-full rounded-md border bg-background px-3"
          value={form.seller_id || ""}
          onChange={(e) => setForm({ ...form, seller_id: e.target.value })}
        >
          <option value="">Choose legal entity</option>
          {(sellers.data || []).map((r: Row) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label htmlFor="billing-contact">Billing contact</Label>
        <select
          id="billing-contact"
          className="h-10 w-full rounded-md border bg-background px-3"
          value={form.contact_id || ""}
          onChange={(e) => setForm({ ...form, contact_id: e.target.value })}
        >
          <option value="">Customer billing email</option>
          {(contacts.data || []).map((r: Row) => (
            <option key={r.id} value={r.id}>
              {r.full_name} — {r.email}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label htmlFor="billing-team">Company team</Label>
        <select
          id="billing-team"
          className="h-10 w-full rounded-md border bg-background px-3"
          value={form.team_id || ""}
          onChange={(e) => setForm({ ...form, team_id: e.target.value })}
        >
          <option value="">No company team</option>
          {(teams.data || [])
            .filter((r: Row) => r.status === "Active")
            .map((r: Row) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
        </select>
      </div>
      <div>
        <Label htmlFor="billing-currency">Currency</Label>
        <Input
          id="billing-currency"
          required
          pattern="[A-Z]{3}"
          value={form.currency}
          onChange={(e) =>
            setForm({ ...form, currency: e.target.value.toUpperCase() })
          }
        />
      </div>
      {showSources && (
        <>
          <div>
            <Label htmlFor="commercial-order">Originating sales order</Label>
            <select
              id="commercial-order"
              className="h-10 w-full rounded-md border bg-background px-3"
              value={form.sales_order_id || ""}
              onChange={(e) =>
                setForm({ ...form, sales_order_id: e.target.value })
              }
            >
              <option value="">Independent project</option>
              {(orders.data || [])
                .filter((r: Row) => r.customer_id === Number(form.customer_id))
                .map((r: Row) => (
                  <option key={r.id} value={r.id}>
                    {r.order_number} — {r.title}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <Label htmlFor="commercial-engagement">
              Originating engagement
            </Label>
            <select
              id="commercial-engagement"
              className="h-10 w-full rounded-md border bg-background px-3"
              value={form.engagement_id || ""}
              onChange={(e) =>
                setForm({ ...form, engagement_id: e.target.value })
              }
            >
              <option value="">No engagement</option>
              {(engagements.data || [])
                .filter((r: Row) => r.customer_id === Number(form.customer_id))
                .map((r: Row) => (
                  <option key={r.id} value={r.id}>
                    {r.engagement_number} — {r.name}
                  </option>
                ))}
            </select>
          </div>
        </>
      )}
      <Button
        type="submit"
        className="self-end"
        disabled={save.isPending || !form.customer_id || !form.seller_id}
      >
        Save billing identity
      </Button>
      {save.isError && (
        <p role="alert" className="text-destructive">
          {errorText(save.error)}
        </p>
      )}
      {save.isSuccess && <p role="status">Billing identity saved.</p>}
    </form>
  );
}

export default function ProjectBillingPage() {
  const { projectId } = useParams();
  const uid = useAuthStore((state) => state.user?.id);
  return (
    <BillingWorkspace
      key={`${uid}-${projectId}`}
      projectId={Number(projectId)}
    />
  );
}

function BillingWorkspace({ projectId }: { projectId: number }) {
  const client = useQueryClient();
  const uid = useAuthStore((state) => state.user?.id);
  const billing = useQuery({
    queryKey: ["project-billing", uid, projectId],
    queryFn: () => read(`/project-management/projects/${projectId}/billing`),
    refetchInterval: 10000,
  });
  const sources = useQuery({
    queryKey: ["billing-sources", uid, projectId],
    queryFn: () =>
      read(`/project-management/projects/${projectId}/billing/sources`),
    enabled: !!billing.data?.can_create,
  });
  const draftKey = `businesssuite-project-invoice-${uid}-${projectId}`;
  const [draft, setDraft] = useState<Row>(() => {
    try {
      return (
        JSON.parse(sessionStorage.getItem(draftKey) || "null") || {
          request_id: crypto.randomUUID(),
          lines: [
            { description: "", quantity: 1, unit_price: 0, tax_amount: 0 },
          ],
          time_log_ids: [],
          time_minutes: {},
          hourly_rate: 0,
        }
      );
    } catch {
      return {
        request_id: crypto.randomUUID(),
        lines: [],
        time_log_ids: [],
        hourly_rate: 0,
      };
    }
  });
  function change(value: Row) {
    setDraft(value);
    sessionStorage.setItem(draftKey, JSON.stringify(value));
  }
  const [created, setCreated] = useState<Row | null>(null);
  const create = useMutation({
    mutationFn: () =>
      api.post(`/project-management/projects/${projectId}/invoices`, {
        ...draft,
        lines: draft.lines.filter((r: Row) => r.description.trim()),
      }),
    onSuccess: (response) => {
      setCreated(response.data);
      sessionStorage.removeItem(draftKey);
      setDraft({
        request_id: crypto.randomUUID(),
        lines: [{ description: "", quantity: 1, unit_price: 0, tax_amount: 0 }],
        time_log_ids: [],
        time_minutes: {},
        hourly_rate: 0,
      });
      client.invalidateQueries({
        queryKey: ["project-billing", uid, projectId],
      });
      client.invalidateQueries({
        queryKey: ["billing-sources", uid, projectId],
      });
    },
  });
  if (billing.isPending) return <p role="status">Loading billing…</p>;
  if (billing.isError)
    return (
      <div role="alert">
        {errorText(billing.error)}{" "}
        <Button onClick={() => billing.refetch()}>Retry</Button>
      </div>
    );
  const data = billing.data;
  return (
    <div className="space-y-6">
      <div>
        <Link to={`/pms/projects/${projectId}`}>← Project</Link>
        <h1 className="page-title">Project billing</h1>
        <p className="text-muted-foreground">
          Invoices, payments and customers shared with Sales.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Commercial identity</CardTitle>
        </CardHeader>
        <CardContent>
          <CommercialIdentityForm
            showSources
            key={JSON.stringify(data.commercial)}
            initial={data.commercial ? { ...data.commercial } : undefined}
            onSave={async (value) => {
              await api.put(
                `/project-management/projects/${projectId}/commercial`,
                value,
              );
              await billing.refetch();
            }}
          />
        </CardContent>
      </Card>
      {data.can_create && (
        <Card>
          <CardHeader>
            <CardTitle>Create invoice draft</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                create.mutate();
              }}
            >
              <fieldset disabled={create.isPending} className="space-y-4">
                {draft.lines.map((line: Row, index: number) => (
                  <div key={index} className="grid gap-2 sm:grid-cols-6">
                    {[
                      "description",
                      "quantity",
                      "unit_price",
                      "discount_amount",
                      "tax_amount",
                    ].map((field) => (
                      <div key={field}>
                        <Label htmlFor={`line-${index}-${field}`}>
                          {field.replace(/_/g, " ")}
                        </Label>
                        <Input
                          id={`line-${index}-${field}`}
                          type={field === "description" ? "text" : "number"}
                          min="0"
                          step="any"
                          value={
                            line[field] ?? (field === "description" ? "" : 0)
                          }
                          onChange={(e) =>
                            change({
                              ...draft,
                              lines: draft.lines.map((l: Row, i: number) =>
                                i === index
                                  ? {
                                      ...l,
                                      [field]:
                                        field === "description"
                                          ? e.target.value
                                          : Number(e.target.value),
                                    }
                                  : l,
                              ),
                            })
                          }
                        />
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        change({
                          ...draft,
                          lines: draft.lines.filter(
                            (_: Row, i: number) => i !== index,
                          ),
                        })
                      }
                    >
                      Remove line
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    change({
                      ...draft,
                      lines: [
                        ...draft.lines,
                        {
                          description: "",
                          quantity: 1,
                          unit_price: 0,
                          tax_amount: 0,
                        },
                      ],
                    })
                  }
                >
                  Add line
                </Button>
                <details>
                  <summary>Bill approved time</summary>
                  <Label htmlFor="hourly-rate">Hourly rate</Label>
                  <Input
                    id="hourly-rate"
                    type="number"
                    min="0"
                    step=".01"
                    value={draft.hourly_rate}
                    onChange={(e) =>
                      change({ ...draft, hourly_rate: Number(e.target.value) })
                    }
                  />
                  {(sources.data?.time_logs || []).map((r: Row) => (
                    <div key={r.id} className="flex items-center gap-2 py-2">
                      <label>
                        <input
                          type="checkbox"
                          checked={draft.time_log_ids.includes(r.id)}
                          onChange={(e) =>
                            change({
                              ...draft,
                              time_log_ids: e.target.checked
                                ? [...draft.time_log_ids, r.id]
                                : draft.time_log_ids.filter(
                                    (id: number) => id !== r.id,
                                  ),
                            })
                          }
                        />{" "}
                        {r.description || `Time log ${r.id}`} (
                        {r.remaining_minutes} min available)
                      </label>
                      <Input
                        aria-label={`Minutes to bill for time log ${r.id}`}
                        className="w-24"
                        type="number"
                        min="1"
                        max={r.remaining_minutes}
                        value={
                          draft.time_minutes?.[r.id] ?? r.remaining_minutes
                        }
                        onChange={(e) =>
                          change({
                            ...draft,
                            time_minutes: {
                              ...draft.time_minutes,
                              [r.id]: Number(e.target.value),
                            },
                          })
                        }
                      />
                    </div>
                  ))}
                  <p>{sources.data?.policy}</p>
                </details>
                <details>
                  <summary>Bill approved milestones</summary>
                  {(sources.data?.milestones || []).map((m: Row) => (
                    <label key={m.id} className="block py-2">
                      <input
                        type="checkbox"
                        checked={(draft.milestone_ids || []).includes(m.id)}
                        onChange={(e) =>
                          change({
                            ...draft,
                            milestone_ids: e.target.checked
                              ? [...(draft.milestone_ids || []), m.id]
                              : draft.milestone_ids.filter(
                                  (id: number) => id !== m.id,
                                ),
                          })
                        }
                      />{" "}
                      {m.name} — {data.commercial?.currency} {m.amount}
                    </label>
                  ))}
                </details>
                <p>
                  Estimated manual-line total: {data.commercial?.currency}{" "}
                  {draft.lines
                    .reduce(
                      (sum: number, l: Row) =>
                        sum +
                        Number(l.quantity) * Number(l.unit_price) -
                        Number(l.discount_amount || 0) +
                        Number(l.tax_amount),
                      0,
                    )
                    .toFixed(2)}
                  . Saved totals are calculated by the server.
                </p>
                <Button
                  type="submit"
                  disabled={create.isPending || !data.commercial}
                >
                  {create.isPending ? "Saving…" : "Save invoice draft"}
                </Button>
                {create.isError && (
                  <p role="alert" className="text-destructive">
                    {errorText(create.error)}
                  </p>
                )}
                {created && (
                  <p role="status">
                    Saved {created.invoice_number}.{" "}
                    <Link
                      className="text-primary underline"
                      to={`/srm/invoices/${created.id}`}
                    >
                      Open in SRM
                    </Link>
                  </p>
                )}
              </fieldset>
            </form>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Invoices and payments</CardTitle>
        </CardHeader>
        <CardContent>
          <InvoiceList
            invoices={data.invoices}
            actions={(row) => (
              <ProjectInvoiceActions
                row={row}
                canIssue={data.can_issue}
                canSend={data.can_send}
                onSaved={() => billing.refetch()}
              />
            )}
          />
          {data.commercial?.sales_order_id && (
            <p>
              <Link to={`/srm/sales-orders/${data.commercial.sales_order_id}`}>
                Originating sales order ↗
              </Link>
            </p>
          )}
          {data.commercial?.opportunity_id && (
            <p>
              <Link to={`/crm/deals/${data.commercial.opportunity_id}`}>
                Originating opportunity ↗
              </Link>
            </p>
          )}
          {data.engagements.map((r: Row) => (
            <p key={r.id}>
              <Link to={`/srm/engagements/${r.id}`}>
                {r.engagement_number} — {r.name}
              </Link>
            </p>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export function InvoiceList({
  invoices,
  actions,
}: {
  invoices: Row[];
  actions?: (row: Row) => ReactNode;
}) {
  return (
    <div className="space-y-3">
      {invoices.length ? (
        invoices.map((row) => (
          <div
            key={row.id}
            role="group"
            aria-label={`Invoice ${row.invoice_number}`}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"
          >
            <Link
              className="font-medium text-primary underline"
              to={`/srm/invoices/${row.id}`}
            >
              {row.invoice_number}
            </Link>
            <span>
              {row.currency} {row.total_amount}
            </span>
            <span>Document: {row.document_status}</span>
            <span>Delivery: {row.delivery_status}</span>
            <span>Payment: {row.payment_status}</span>
            <span>Outstanding: {row.balance_amount}</span>
            {row.project_id && (
              <Link to={`/pms/projects/${row.project_id}/billing`}>
                Project billing ↗
              </Link>
            )}
            {actions?.(row)}
          </div>
        ))
      ) : (
        <p>No invoices yet.</p>
      )}
    </div>
  );
}

function ProjectInvoiceActions({
  row,
  canIssue,
  canSend,
  onSaved,
}: {
  row: Row;
  canIssue: boolean;
  canSend: boolean;
  onSaved: () => unknown;
}) {
  const [notice, setNotice] = useState("");
  const action = useMutation({
    mutationFn: async (name: string) =>
      (await api.post(`/srm/invoices/${row.id}/${name}`)).data,
    onSuccess: (data) => {
      setNotice(
        data.delivery
          ? `Delivery: ${data.delivery.status}. ${data.delivery.error || ""}`
          : "Invoice issued.",
      );
      onSaved();
    },
  });
  const pdf = useMutation({
    mutationFn: async () =>
      (await api.get(`/srm/invoices/${row.id}/pdf`, { responseType: "blob" }))
        .data,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${row.invoice_number}.pdf`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    },
  });
  return (
    <div className="w-full space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={pdf.isPending}
          onClick={() => pdf.mutate()}
        >
          PDF preview
        </Button>
        {canIssue && row.document_status === "draft" && (
          <Button
            size="sm"
            disabled={action.isPending}
            onClick={() => action.mutate("approve")}
          >
            Issue invoice
          </Button>
        )}
        {canSend &&
          row.document_status === "issued" &&
          !["sent", "sending", "unknown"].includes(row.delivery_status) && (
            <Button
              size="sm"
              disabled={action.isPending}
              onClick={() => action.mutate("send")}
            >
              {["failed", "blocked"].includes(row.delivery_status)
                ? "Retry delivery"
                : "Send invoice"}
            </Button>
          )}
      </div>
      {notice && <p role="status">{notice}</p>}
      {action.isError && <p role="alert">{errorText(action.error)}</p>}
      {pdf.isError && <p role="alert">Unable to preview this invoice.</p>}
    </div>
  );
}
