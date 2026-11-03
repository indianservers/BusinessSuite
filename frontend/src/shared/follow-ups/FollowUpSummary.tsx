import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
export default function FollowUpSummary({ base }: { base: string }) {
  const q = useQuery({
    queryKey: ["follow-ups", "statistics"],
    queryFn: () => api.get("/follow-ups/statistics").then((r) => r.data),
    refetchInterval: 60000,
  });
  if (!q.data) return null;
  return (
    <aside className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-3 text-sm">
      <strong>Customer service commitments</strong>
      <div className="flex flex-wrap gap-4">
        <span className="text-red-700">{q.data.Overdue} overdue</span>
        <span>{q.data.Due} due today</span>
        <span>{q.data["Upcoming 7 Days"]} in the next 7 days</span>
        <Link className="font-medium text-primary underline" to={base}>
          Open follow-ups
        </Link>
      </div>
    </aside>
  );
}
