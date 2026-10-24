import { useAuthStore } from "@/store/authStore";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { InvoiceList } from "@/apps/project-management/pages/ProjectBillingPage";

export default function CustomerCommercialHistory({
  customerId,
}: {
  customerId: number;
}) {
  const uid = useAuthStore((state) => state.user?.id);
  const query = useQuery({
    queryKey: ["customer-commercial-history", uid, customerId],
    queryFn: async () =>
      (await api.get(`/srm/business/customers/${customerId}/history`)).data,
    enabled: customerId > 0,
    refetchInterval: 10000,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Customer commercial history</CardTitle>
      </CardHeader>
      <CardContent>
        {!customerId ? (
          <p>
            Link this legacy account to a shared customer through reconciliation
            to show commercial history.
          </p>
        ) : query.isPending ? (
          <p>Loading commercial history…</p>
        ) : query.isError ? (
          <p>
            Financial history requires invoice viewing permission and customer
            access.
          </p>
        ) : (
          <div className="space-y-4">
            <InvoiceList invoices={query.data.invoices} />
            {query.data.projects.map((p: any) => (
              <p key={p.id}>
                <Link to={`/pms/projects/${p.id}`}>{p.name} ↗</Link>
              </p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
