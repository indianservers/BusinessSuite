import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { srmApi } from "../api";
import type { SRMRecord } from "../types";

type DetailKind = "salesOrder" | "contract" | "engagement" | "billingPlan";

const loaders: Record<DetailKind, (id: number) => Promise<SRMRecord>> = {
  salesOrder: srmApi.salesOrder,
  contract: srmApi.contract,
  engagement: srmApi.engagement,
  billingPlan: srmApi.billingPlan,
};

const titles: Record<DetailKind, string> = {
  salesOrder: "Sales Order Detail",
  contract: "Contract Detail",
  engagement: "Engagement Detail",
  billingPlan: "Billing Plan Detail",
};

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return Array.isArray(value) ? `${value.length}` : "Linked";
  return String(value).replace(/_/g, " ");
}

export default function SRMCommercialDetailPage({ kind }: { kind: DetailKind }) {
  const { id } = useParams();
  const numericId = Number(id || 0);
  const query = useQuery({
    queryKey: ["srm", kind, numericId],
    queryFn: () => loaders[kind](numericId),
    enabled: numericId > 0,
  });
  const record = (query.data || {}) as SRMRecord;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titles[kind]}</h1>
        <p className="text-sm text-muted-foreground">Linked commercial lifecycle record.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {formatValue(record.order_number || record.contract_number || record.engagement_number || record.name || record.title || `Record ${numericId}`)}
            {record.status ? <Badge>{formatValue(record.status)}</Badge> : null}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {["customer_id", "crm_deal_id", "sales_order_id", "engagement_id", "contract_value", "total_amount", "budget_amount", "pms_project_id"].map((key) => (
            <div key={key} className="rounded-lg border p-3">
              <p className="text-xs uppercase text-muted-foreground">{key.replace(/_/g, " ")}</p>
              <p className="mt-1 text-sm font-medium">{formatValue(record[key])}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
