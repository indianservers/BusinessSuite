import PhoneActions from "@/components/PhoneActions";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/services/api";
import SharedDataGrid from "@/shared/data-grid/SharedDataGrid";
import type {
  GridDataSource,
  GridColumn,
  GridQuery,
} from "@/shared/data-grid/types";
type Row = Record<string, any>;
export default function FollowUpGrid({
  base,
  refreshKey,
  onSelectionChange,
}: {
  base: string;
  refreshKey: number;
  onSelectionChange: (ids: number[]) => void;
}) {
  const user = useAuthStore((s) => s.user);
  const source = useMemo<GridDataSource<Row>>(
    () => ({
      key: "shared-follow-ups",
    personalIdentity: "id",
      load: async (query, signal) =>
        (
          await api.get("/follow-ups/grid/query", {
            params: { state: JSON.stringify(query) },
            signal,
            progress: false,
          })
        ).data,
      export: async (request) => {
        if (!["csv", "clipboard"].includes(request.format))
          throw new Error("Choose CSV or clipboard export for follow-ups.");
        const query: GridQuery = {
          ...request.query,
          grouping: [],
          path: [],
          page: 1,
          pageSize: 200,
        };
        const items: Row[] = [];
        let total = Infinity;
        while (items.length < total) {
          const result = (
            await api.get("/follow-ups/grid/query", {
              params: { state: JSON.stringify(query) },
              progress: false,
            })
          ).data;
          total = result.total;
          if (total > 20000)
            throw new Error(
              "Export is limited to 20,000 records; narrow your filters.",
            );
          items.push(...result.rows);
          if (!result.rows.length) break;
          query.page++;
        }
        const selected =
          request.scope === "selected"
            ? items.filter((r) => request.ids.includes(String(r.id)))
            : items;
        const columns = request.columns;
        const cell = (v: unknown) =>
          '"' +
          String(v ?? "")
            .replace(/"/g, '""')
            .replace(/^[=+@-]/, "'$&") +
          '"';
        return new Blob(
          [
            columns.map(cell).join(",") +
              "\r\n" +
              selected
                .map((r) => columns.map((c) => cell(r[c])).join(","))
                .join("\r\n"),
          ],
          { type: "text/csv" },
        );
      },
    }),
    [],
  );
  const columns: GridColumn<Row>[] = useMemo(
    () => [
      {
        id: "customer_name",
        title: "Customer",
        width: 210,
        render: (r) => (
          <>
            <Link
              className="text-primary"
              to={`/crm/companies/${r.customer_id}`}
            >
              {r.customer_name}
            </Link>
            <small className="block"><PhoneActions value={r.phone} record={r} field="phone" /></small>
          </>
        ),
      },
      {
        id: "title",
        title: "Product / service & next action",
        width: 270,
        render: (r) => (
          <Link className="text-primary underline" to={`${base}/${r.id}`}>
            {r.title}
          </Link>
        ),
      },
      {
        id: "order_id",
        title: "Transaction",
        type: "number",
        render: (r) =>
          r.order_id ? (
            <Link to={`/srm/sales-orders/${r.order_id}`}>
              Order #{r.order_id}
            </Link>
          ) : (
            "Manual"
          ),
      },
      { id: "due_at", title: "Follow-up date", type: "datetime", width: 210 },
      { id: "assigned_to", title: "Assigned to", type: "owner", width: 220 },
      { id: "priority", title: "Priority", type: "status" },
      { id: "status", title: "Status", type: "status" },
      {
        id: "last_contact",
        title: "Last contact",
        sortable: false,
        filterable: false,
        groupable: false,
        render: (r) =>
          r.last_contact
            ? new Date(r.last_contact).toLocaleString()
            : "No contact logged",
      },
      {
        id: "contact",
        title: "Contact",
        sortable: false,
        filterable: false,
        groupable: false,
        render: (r) =>
          r.phone ? (
            <div className="flex gap-3">
              <a
                className="underline"
                href={`tel:${r.phone.replace(/[^\d+]/g, "")}`}
              >
                Call
              </a>
              <a
                className="underline"
                href={`https://wa.me/${r.phone.replace(/\D/g, "")}`}
                target="_blank"
                rel="noreferrer"
              >
                WhatsApp
              </a>
            </div>
          ) : (
            "—"
          ),
      },
    ],
    [base],
  );
  return (
    <SharedDataGrid
      gridId="service-follow-ups"
      title="Follow-up directory"
      userId={Number(user?.id) || undefined}
      organizationId={user?.access?.companyId}
      columns={columns}
      dataSource={source}
      refreshKey={refreshKey}
      getRowId={(r) => String(r.id)}
      onSelectionChange={(_rows, ids) => onSelectionChange(ids.map(Number))}
      views={["grid", "list", "cards"]}
      height={620}
      rowActions={[
        {
          id: "open",
          label: "View / edit follow-up",
          run: (r) => {
            window.location.assign(`${base}/${r.id}`);
          },
        },
      ]}
    />
  );
}
