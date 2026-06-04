import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Download, FileImage, FileText, Minus, Plus, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { usePageTitle } from "@/hooks/use-page-title";
import { companyApi } from "@/services/api";

type OrgNode = {
  position_id: number;
  position_code: string;
  title: string;
  manager_position_id?: number | null;
  incumbent_employee_id?: number | null;
  employee_name?: string | null;
  employee_code?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  grade_band_id?: number | null;
  grade_band_name?: string | null;
  designation_name?: string | null;
  status: string;
  is_vacant: boolean;
  x?: number;
  y?: number;
};

const NODE_W = 230;
const NODE_H = 104;
const GAP_X = 34;
const GAP_Y = 86;

function layout(nodes: OrgNode[]) {
  const byManager = new Map<number | null, OrgNode[]>();
  nodes.forEach((node) => {
    const key = node.manager_position_id && nodes.some((item) => item.position_id === node.manager_position_id) ? node.manager_position_id : null;
    byManager.set(key, [...(byManager.get(key) || []), node]);
  });
  let cursor = 0;
  const positioned: OrgNode[] = [];

  function visit(node: OrgNode, depth: number): number {
    const children = byManager.get(node.position_id) || [];
    if (!children.length) {
      node.x = cursor * (NODE_W + GAP_X);
      cursor += 1;
    } else {
      const childCenters = children.map((child) => visit(child, depth + 1));
      node.x = (Math.min(...childCenters) + Math.max(...childCenters)) / 2;
    }
    node.y = depth * (NODE_H + GAP_Y);
    positioned.push(node);
    return node.x;
  }

  (byManager.get(null) || []).forEach((root) => visit(root, 0));
  return positioned;
}

export default function OrgChartPage() {
  usePageTitle("Org Chart");
  const navigate = useNavigate();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [departmentId, setDepartmentId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [gradeBandId, setGradeBandId] = useState("");
  const [zoom, setZoom] = useState(0.9);
  const [loadRequested, setLoadRequested] = useState(false);

  const departments = useQuery({ queryKey: ["org-departments"], queryFn: () => companyApi.listDepartments().then((r) => r.data) });
  const locations = useQuery({ queryKey: ["org-locations"], queryFn: () => companyApi.workLocations().then((r) => r.data) });
  const gradeBands = useQuery({ queryKey: ["org-grade-bands"], queryFn: () => companyApi.gradeBands().then((r) => r.data) });
  const org = useQuery({
    queryKey: ["org-chart", departmentId, locationId, gradeBandId],
    queryFn: () =>
      companyApi.orgChart({
        department_id: departmentId || undefined,
        location_id: locationId || undefined,
        grade_band_id: gradeBandId || undefined,
      }).then((r) => r.data as OrgNode[]),
    enabled: loadRequested,
    retry: false,
  });

  const nodes = useMemo(() => layout([...(org.data || [])]), [org.data]);
  const width = Math.max(960, ...nodes.map((node) => (node.x || 0) + NODE_W + 80));
  const height = Math.max(520, ...nodes.map((node) => (node.y || 0) + NODE_H + 80));
  const byId = new Map(nodes.map((node) => [node.position_id, node]));

  const exportSvg = () => {
    if (!svgRef.current) return;
    const blob = new Blob([new XMLSerializer().serializeToString(svgRef.current)], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "org-chart.svg";
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportPng = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "#94a3b8";
    nodes.forEach((node) => {
      const parent = node.manager_position_id ? byId.get(node.manager_position_id) : null;
      if (parent) {
        ctx.beginPath();
        ctx.moveTo((parent.x || 0) + NODE_W / 2, (parent.y || 0) + NODE_H);
        ctx.lineTo((node.x || 0) + NODE_W / 2, node.y || 0);
        ctx.stroke();
      }
    });
    nodes.forEach((node) => {
      const x = node.x || 0;
      const y = node.y || 0;
      ctx.setLineDash(node.is_vacant ? [7, 5] : []);
      ctx.strokeStyle = node.is_vacant ? "#f59e0b" : "#2563eb";
      ctx.fillStyle = node.is_vacant ? "#fffbeb" : "#eff6ff";
      ctx.fillRect(x, y, NODE_W, NODE_H);
      ctx.strokeRect(x, y, NODE_W, NODE_H);
      ctx.setLineDash([]);
      ctx.fillStyle = "#111827";
      ctx.font = "600 14px Arial";
      ctx.fillText(node.title.slice(0, 28), x + 14, y + 26);
      ctx.font = "12px Arial";
      ctx.fillText((node.employee_name || "Vacant").slice(0, 30), x + 14, y + 52);
      ctx.fillText(`${node.department_name || "-"} - ${node.grade_band_name || "-"}`.slice(0, 34), x + 14, y + 76);
    });
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = "org-chart.png";
    a.click();
  };

  return (
    <div className="space-y-5">
      <div className="rounded-lg border bg-card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Organization</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Real-Time Org Chart</h1>
            <p className="mt-1 text-sm text-muted-foreground">Live position hierarchy with vacancies, filters, exports, and employee profile drill-down.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setZoom((v) => Math.max(0.45, v - 0.1))} title="Zoom out"><Minus className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" onClick={() => setZoom((v) => Math.min(1.5, v + 0.1))} title="Zoom in"><Plus className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" onClick={() => setZoom(0.9)} title="Reset zoom"><RotateCcw className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" onClick={() => setLoadRequested(true)}><RotateCcw className="h-4 w-4" />Load chart</Button>
            <Button variant="outline" size="sm" onClick={() => window.print()}><FileText className="h-4 w-4" />PDF</Button>
            <Button variant="outline" size="sm" onClick={exportPng}><FileImage className="h-4 w-4" />PNG</Button>
            <Button variant="outline" size="sm" onClick={exportSvg}><Download className="h-4 w-4" />SVG</Button>
          </div>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-3">
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">All departments</option>
            {departments.data?.map((item: { id: number; name: string }) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
            <option value="">All locations</option>
            {locations.data?.map((item: { id: number; name: string }) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select className="h-10 rounded-md border bg-background px-3 text-sm" value={gradeBandId} onChange={(e) => setGradeBandId(e.target.value)}>
            <option value="">All grade bands</option>
            {gradeBands.data?.map((item: { id: number; name: string }) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </CardContent>
      </Card>

      <div className="overflow-auto rounded-lg border bg-white p-4 org-chart-export">
        <svg ref={svgRef} width={width * zoom} height={height * zoom} viewBox={`-40 -30 ${width} ${height}`} role="img" aria-label="Organization chart">
          {nodes.map((node) => {
            const parent = node.manager_position_id ? byId.get(node.manager_position_id) : null;
            if (!parent) return null;
            return <path key={`l-${node.position_id}`} d={`M ${(parent.x || 0) + NODE_W / 2} ${(parent.y || 0) + NODE_H} V ${(parent.y || 0) + NODE_H + GAP_Y / 2} H ${(node.x || 0) + NODE_W / 2} V ${node.y || 0}`} fill="none" stroke="#94a3b8" strokeWidth="1.5" />;
          })}
          {!loadRequested && (
            <text x="20" y="40" fontSize="14" fill="#64748b">Use Load chart to fetch the live organization hierarchy.</text>
          )}
          {nodes.map((node) => (
            <g key={node.position_id} transform={`translate(${node.x || 0},${node.y || 0})`} onClick={() => node.incumbent_employee_id && navigate(`/hrms/employees/${node.incumbent_employee_id}`)} className={node.incumbent_employee_id ? "cursor-pointer" : ""}>
              <rect width={NODE_W} height={NODE_H} rx="8" fill={node.is_vacant ? "#fffbeb" : "#eff6ff"} stroke={node.is_vacant ? "#f59e0b" : "#2563eb"} strokeWidth="1.8" strokeDasharray={node.is_vacant ? "8 5" : undefined} />
              <text x="14" y="24" fontSize="14" fontWeight="700" fill="#111827">{node.title.slice(0, 28)}</text>
              <text x="14" y="46" fontSize="12" fill="#334155">{(node.employee_name || "Vacant position").slice(0, 31)}</text>
              <text x="14" y="66" fontSize="11" fill="#64748b">{(node.department_name || "No department").slice(0, 26)}</text>
              <text x="14" y="84" fontSize="11" fill="#64748b">{`${node.grade_band_name || "-"} - ${node.location_name || "-"}`.slice(0, 29)}</text>
            </g>
          ))}
        </svg>
      </div>

      <div className="flex flex-wrap gap-2 text-sm">
        <Badge variant="outline">{nodes.length} positions</Badge>
        <Badge variant="outline">{nodes.filter((item) => item.is_vacant).length} vacant</Badge>
        <Badge variant="outline">{Math.round(zoom * 100)}% zoom</Badge>
      </div>
    </div>
  );
}
