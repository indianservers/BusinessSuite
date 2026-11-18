import GridTable from "@/shared/data-grid/GridTable";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Metric {
  label: string;
  value: string;
}

interface WorkItem {
  title: string;
  description: string;
  status: string;
}

export default function ModuleShell({
  title,
  description,
  icon: Icon,
  metrics,
  items,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  metrics: Metric[];
  items: WorkItem[];
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="page-title">{title}</h1>
          <p className="page-description">{description}</p>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent className="p-5">
              <p className="text-sm text-muted-foreground">{metric.label}</p>
              <p className="mt-2 text-2xl font-semibold">{metric.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Workspace</CardTitle>
          <CardDescription>Operational queue and recent activity</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <GridTable gridId="components/ModuleShell:table-1" className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-3 font-medium">Item</th>
                  <th className="py-3 font-medium">Details</th>
                  <th className="py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr {...recordPreviewProps(item)} key={item.title} className="border-b last:border-0">
                    <td className="py-3 font-medium">{item.title}</td>
                    <td className="py-3 text-muted-foreground">{item.description}</td>
                    <td className="py-3">
                      <Badge variant="secondary">{item.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </GridTable>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
