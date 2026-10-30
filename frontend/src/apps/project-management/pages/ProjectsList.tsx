import { useRefreshableEffect } from "@/lib/page-refresh";
import { CustomFieldCell, FieldValue, useCustomFieldRecords, type CustomField } from "../components/CustomFields";
import { api } from "@/services/api";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import RecordActions from "../components/RecordActions";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CalendarDays, Kanban, Plus, Search, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatCurrency, formatDate, statusColor } from "@/lib/utils";
import { projectsAPI } from "../services/api";
import { useProjectStore } from "../store";
import type { PMSProject } from "../types";

export default function ProjectsList() {
  const navigate = useNavigate();
  const { projects, setProjects, setSelectedProject } = useProjectStore();
  const custom=useCustomFieldRecords("project",projects.map(p=>p.id));
  const [customFields,setCustomFields]=useState<CustomField[]>([]);
  const [table,setTable]=useState(false),[columnsOpen,setColumnsOpen]=useState(false);
  const [hiddenFields,setHiddenFields]=useState<number[]>(()=>{try{return JSON.parse(localStorage.getItem("pms.project-hidden-fields.v1")||"[]");}catch{return [];}});
  useEffect(()=>{try{localStorage.setItem("pms.project-hidden-fields.v1",JSON.stringify(hiddenFields));}catch{/* optional browser preference */}},[hiddenFields]);
  useRefreshableEffect(()=>{let active=true;api.get<{fields:CustomField[]}>("/project-management/custom-fields").then(({data})=>{if(active)setCustomFields(data.fields.filter(f=>f.entity_type!=="task"));}).catch(()=>undefined);return()=>{active=false;};},[]);
  const shownFields=customFields.filter(f=>!hiddenFields.includes(f.id));
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useRefreshableEffect(() => {
    projectsAPI
      .list()
      .then(setProjects)
      .catch((err) => setError(err?.response?.data?.detail || "Unable to load projects."))
      .finally(() => setLoading(false));
  }, [setProjects]);

  const filtered = useMemo(
    () => projects.filter((project) => `${project.name} ${project.project_key}`.toLowerCase().includes(query.toLowerCase())),
    [projects, query]
  );

  const openProject = (project: PMSProject) => {
    setSelectedProject(project);
    navigate(`/pms/projects/${project.id}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-description">Track active work, ownership, progress, budgets, and delivery risk.</p>
          <Link className="text-sm underline" to="/pms/management?view=projects">Manage projects: filters, owners, milestones, bulk actions & duplication</Link>
        </div>
        <div className="flex gap-2"><Button variant="outline" asChild><Link to="/pms/trash?type=projects"><Trash2 className="h-4 w-4" />Trash</Link></Button><Button asChild>
          <Link to="/pms/projects/new"><Plus className="h-4 w-4" />New project</Link>
        </Button></div>
      </div>

      <div className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search projects" className="border-0 shadow-none focus-visible:ring-0" />
      </div>

      <div className="flex flex-wrap gap-2"><Button variant={table?"outline":"secondary"} size="sm" onClick={()=>setTable(false)}>Cards</Button><Button variant={table?"secondary":"outline"} size="sm" onClick={()=>setTable(true)}>Table</Button><Button variant="outline" size="sm" onClick={()=>setColumnsOpen(v=>!v)} aria-expanded={columnsOpen}>Custom columns</Button><Button asChild size="sm" variant="ghost"><Link to="/pms/custom-fields?entity=project&create=1">+ Add custom column</Link></Button></div>
      {columnsOpen&&<div className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-3">{customFields.map(f=><label key={f.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!hiddenFields.includes(f.id)} onChange={e=>setHiddenFields(v=>e.target.checked?v.filter(id=>id!==f.id):[...v,f.id])}/>{f.name}</label>)}{!customFields.length&&<p className="text-sm text-muted-foreground">Create a project field to add your first custom column.</p>}</div>}
      {custom.error&&<p role="alert" className="text-sm text-destructive">{custom.error}</p>}
      {table&&<div className="overflow-x-auto rounded-xl border bg-card"><table className="w-full text-left text-sm"><thead className="border-b bg-muted/30"><tr><th className="p-4">Project</th><th className="p-4">Status</th><th className="p-4">Due date</th>{shownFields.map(f=><th key={f.id} className="min-w-44 p-4">{f.name}</th>)}</tr></thead><tbody>{filtered.map(p=><tr key={p.id} className="border-b last:border-0 hover:bg-muted/10"><td className="p-4"><Link className="font-medium text-primary" to={`/pms/projects/${p.id}`}>{p.name}</Link><p className="text-xs text-muted-foreground">{p.project_key}</p></td><td className="p-4"><Badge className={statusColor(p.status)}>{p.status}</Badge></td><td className="p-4">{formatDate(p.due_date||null)}</td>{shownFields.map(f=>{const record=custom.records[p.id];const field=record?.fields.find(item=>item.id===f.id);return <td key={f.id} className="p-4">{field?<CustomFieldCell entity="project" id={p.id} field={field} canEdit={record.can_edit} onSaved={custom.reload}/>:"—"}</td>;})}</tr>)}</tbody></table>{!filtered.length&&!loading&&<p className="p-8 text-center text-muted-foreground">No projects found.</p>}</div>}
      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {loading ? <div className="skeleton h-40 rounded-lg" /> : null}

      <div className={table?"hidden":"grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"}>
        {filtered.map((project) => (
          <RecordActions key={project.id} kind="project" canEdit={project.can_edit_project === true} onChanged={async()=>{setProjects(await projectsAPI.list());}} record={{...project,title:project.name,key:project.project_key}} onOpen={()=>openProject(project)}>{menu=><Card data-testid={`project-card-${project.id}`} tabIndex={0} className="min-w-0 cursor-pointer transition hover:border-primary/40 hover:shadow-md">
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{project.project_key}</p>
                  <h2 className="mt-1 truncate text-lg font-semibold"><button type="button" className="text-left hover:text-primary" onClick={()=>openProject(project)}>{project.name}</button></h2>
                </div>
                <div className="flex items-center gap-1"><Badge className={statusColor(project.status)}>{project.status}</Badge>{menu}</div>
              </div>
              <div className="mt-3 line-clamp-2 min-h-10 text-sm text-muted-foreground"><RichTextContent value={project.description || "No description added yet."}/></div>
              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Progress</span>
                  <span>{project.progress_percent}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-primary" style={{ width: `${project.progress_percent}%` }} />
                </div>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-lg bg-muted/60 p-3">
                  <p className="text-xs text-muted-foreground">Health</p>
                  <p className="font-medium">{project.health}</p>
                </div>
                <div className="rounded-lg bg-muted/60 p-3">
                  <p className="text-xs text-muted-foreground">Budget</p>
                  <p className="font-medium">{formatCurrency(Number(project.budget_amount || 0))}</p>
                </div>
              </div>
              <div className="mt-4 grid gap-2">{custom.records[project.id]?.fields.filter(f=>!hiddenFields.includes(f.id)).map(f=><div key={f.id} className="flex items-start justify-between gap-3 rounded-lg bg-muted/20 px-3 py-2 text-xs"><span className="text-muted-foreground">{f.name}</span><FieldValue field={f}/></div>)}</div>
              <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{formatDate(project.due_date || null)}</span>
                <Link to={`/pms/projects/${project.id}/board`} onClick={(event) => event.stopPropagation()} className="inline-flex items-center gap-1 font-medium text-primary">
                  <Kanban className="h-3.5 w-3.5" />Board
                </Link>
              </div>
            </CardContent>
          </Card>}</RecordActions>
        ))}
      </div>
    </div>
  );
}

