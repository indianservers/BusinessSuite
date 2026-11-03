import { ActionButton } from "@/components/actions";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
export default function CustomerFollowUps({
  customerId,
}: {
  customerId: number;
}) {
  const q = useQuery({
    queryKey: ["follow-ups", "customer", customerId],
    queryFn: () =>
      api
        .get("/follow-ups", {
          params: { customer_id: customerId, per_page: 10 },
        })
        .then((r) => r.data),
    enabled: customerId > 0,
  });
  return (
    <section className="space-y-2 rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">Service follow-ups</h2>
        <ActionButton action="followup" asChild tooltip="Schedule a follow-up for this customer"><Link
          to={`/crm/follow-ups?customer=${customerId}&new=1`}
        >
          Schedule follow-up
        </Link></ActionButton>
      </div>
      {q.isLoading && <p role="status">Loading commitments…</p>}
      {q.isError && (
        <p role="alert">
          Follow-ups unavailable for this record or your access level.
        </p>
      )}
      {q.data?.items.map((r: any) => (
        <Link
          key={r.id}
          className="flex justify-between gap-2 rounded border p-2 text-sm"
          to={`/crm/follow-ups/${r.id}`}
        >
          <span>{r.title}</span>
          <span>
            {new Date(r.due_at).toLocaleString()} · {r.status}
          </span>
        </Link>
      ))}
      {q.data?.total === 0 && (
        <p className="text-sm text-muted-foreground">
          No scheduled service follow-ups.
        </p>
      )}
      {q.data?.total > 10 && (
        <Link
          to={`/crm/follow-ups/directory?customer=${customerId}`}
          className="text-sm underline"
        >
          View all {q.data.total} commitments
        </Link>
      )}
    </section>
  );
}
