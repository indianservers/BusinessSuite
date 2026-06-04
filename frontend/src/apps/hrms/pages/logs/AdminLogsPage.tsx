import { useState } from "react";
import type React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Activity, RefreshCw, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePageTitle } from "@/hooks/use-page-title";
import { logsApi } from "@/services/api";

type AuditLog = {
  id: number;
  user_id?: number | null;
  method: string;
  endpoint?: string | null;
  status_code?: number | null;
  duration_ms?: number | null;
  ip_address?: string | null;
  action?: string | null;
  description?: string | null;
  created_at: string;
};

type LogAnalysis = {
  total_requests: number;
  error_count: number;
  server_error_count: number;
  error_rate_percent: number;
  avg_duration_ms: number;
  by_status: Array<{ status_code: number; count: number }>;
  top_errors: Array<{ endpoint: string; status_code: number; count: number }>;
  slow_endpoints: Array<{ endpoint: string; avg_ms: number; count: number }>;
};

type FieldAuditEvent = {
  id: number;
  module: string;
  employee_id?: number | null;
  field_name: string;
  action?: string | null;
  old_value_masked?: string | null;
  new_value_masked?: string | null;
  actor_user_id?: number | null;
  created_at: string;
};

function statusVariant(status?: number | null) {
  if (!status) return "secondary";
  if (status >= 500) return "destructive";
  if (status >= 400) return "secondary";
  return "default";
}

export default function AdminLogsPage() {
  usePageTitle("Audit Logs");
  const [endpoint, setEndpoint] = useState("attendance");
  const [employeeId, setEmployeeId] = useState("");
  const [fieldName, setFieldName] = useState("");
  const [errorsOnly, setErrorsOnly] = useState(true);
  const params = { endpoint: endpoint || undefined, limit: 100 };

  const logs = useQuery({
    queryKey: ["admin-logs", endpoint, errorsOnly],
    queryFn: () =>
      (errorsOnly ? logsApi.errors(params) : logsApi.audit(params)).then((r) => r.data as AuditLog[]),
  });

  const analysis = useQuery({
    queryKey: ["admin-log-analysis", endpoint],
    queryFn: () => logsApi.analysis({ endpoint: endpoint || undefined }).then((r) => r.data as LogAnalysis),
  });

  const fieldAudit = useQuery({
    queryKey: ["field-audit", employeeId, fieldName],
    queryFn: () => logsApi.fieldAudit({
      employee_id: employeeId || undefined,
      field_name: fieldName || undefined,
      limit: 100,
    }).then((r) => r.data as FieldAuditEvent[]),
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Admin logs</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Request logs and error analysis</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Review failed API calls, slow endpoints, status codes, and recent request history.
          </p>
        </div>
        <Button variant="outline" onClick={() => { logs.refetch(); analysis.refetch(); }}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Metric title="Requests" value={analysis.data?.total_requests ?? 0} icon={Activity} />
        <Metric title="Errors" value={analysis.data?.error_count ?? 0} icon={AlertTriangle} />
        <Metric title="Server Errors" value={analysis.data?.server_error_count ?? 0} icon={AlertTriangle} />
        <Metric title="Error Rate" value={`${analysis.data?.error_rate_percent ?? 0}%`} icon={Activity} />
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={endpoint}
              onChange={(event) => setEndpoint(event.target.value)}
              placeholder="Filter endpoint, e.g. attendance/check-in"
              className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <Button variant={errorsOnly ? "default" : "outline"} onClick={() => setErrorsOnly((value) => !value)}>
            Errors only
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Sensitive HR Field Audit</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-[160px_220px_auto]">
            <input
              value={employeeId}
              onChange={(event) => setEmployeeId(event.target.value)}
              placeholder="Employee ID"
              className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <select
              value={fieldName}
              onChange={(event) => setFieldName(event.target.value)}
              className="h-9 rounded-md border bg-background px-3 text-sm"
            >
              <option value="">All fields</option>
              {["ctc", "basic", "hra", "account_number", "ifsc_code", "pan_number", "aadhaar_number", "reporting_manager_id", "designation_id", "department_id", "work_location", "status"].map((field) => (
                <option key={field} value={field}>{field}</option>
              ))}
            </select>
            <Button variant="outline" onClick={() => fieldAudit.refetch()}>Refresh Field Audit</Button>
          </div>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="border-b bg-muted/50">
                <tr>{["Time", "Module", "Employee", "Field", "Old", "New", "Actor", "Action"].map((heading) => <th key={heading} className="px-3 py-2 text-left text-xs uppercase text-muted-foreground">{heading}</th>)}</tr>
              </thead>
              <tbody>
                {(fieldAudit.data || []).map((event) => (
                  <tr key={event.id} className="border-b">
                    <td className="whitespace-nowrap px-3 py-2 text-muted-foreground">{new Date(event.created_at).toLocaleString()}</td>
                    <td className="px-3 py-2">{event.module}</td>
                    <td className="px-3 py-2">{event.employee_id ?? "-"}</td>
                    <td className="px-3 py-2 font-medium">{event.field_name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{event.old_value_masked || "-"}</td>
                    <td className="px-3 py-2 text-muted-foreground">{event.new_value_masked || "-"}</td>
                    <td className="px-3 py-2">{event.actor_user_id ?? "-"}</td>
                    <td className="px-3 py-2"><Badge variant="outline">{event.action || "updated"}</Badge></td>
                  </tr>
                ))}
                {!fieldAudit.isLoading && (fieldAudit.data || []).length === 0 && (
                  <tr><td colSpan={8} className="px-3 py-6 text-center text-muted-foreground">No field audit events found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top errors</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(analysis.data?.top_errors || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No errors for this filter.</p>
            ) : (
              analysis.data!.top_errors.map((item) => (
                <div key={`${item.endpoint}-${item.status_code}`} className="flex items-center justify-between rounded-md border p-3 text-sm">
                  <span className="truncate">{item.endpoint}</span>
                  <div className="flex items-center gap-2">
                    <Badge variant={statusVariant(item.status_code)}>{item.status_code}</Badge>
                    <span className="text-muted-foreground">{item.count}</span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Slow endpoints</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(analysis.data?.slow_endpoints || []).map((item) => (
              <div key={item.endpoint} className="flex items-center justify-between rounded-md border p-3 text-sm">
                <span className="truncate">{item.endpoint}</span>
                <span className="text-muted-foreground">{item.avg_ms} ms</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent logs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="border-b bg-muted/50">
                <tr>
                  {["Time", "Method", "Endpoint", "Status", "Duration", "User", "Details"].map((heading) => (
                    <th key={heading} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(logs.data || []).map((log) => (
                  <tr key={log.id} className="border-b align-top">
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{new Date(log.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 font-medium">{log.method}</td>
                    <td className="max-w-[300px] truncate px-4 py-3">{log.endpoint}</td>
                    <td className="px-4 py-3"><Badge variant={statusVariant(log.status_code)}>{log.status_code}</Badge></td>
                    <td className="px-4 py-3 text-muted-foreground">{log.duration_ms ?? 0} ms</td>
                    <td className="px-4 py-3 text-muted-foreground">{log.user_id ?? "-"}</td>
                    <td className="max-w-[360px] px-4 py-3 text-muted-foreground">{log.description || "-"}</td>
                  </tr>
                ))}
                {!logs.isLoading && (logs.data || []).length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">No logs found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ title, value, icon: Icon }: { title: string; value: string | number; icon: React.ElementType }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div>
          <p className="text-xs text-muted-foreground">{title}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
        </div>
        <Icon className="h-5 w-5 text-muted-foreground" />
      </CardContent>
    </Card>
  );
}
