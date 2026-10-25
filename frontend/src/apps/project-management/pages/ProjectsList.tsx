import RecordActions from "../components/RecordActions";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CalendarDays, Kanban, Plus, Search } from "lucide-react";
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
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
        </div>
        <Button asChild>
          <Link to="/pms/projects/new"><Plus className="h-4 w-4" />New project</Link>
        </Button>
      </div>

      <div className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search projects" className="border-0 shadow-none focus-visible:ring-0" />
      </div>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {loading ? <div className="skeleton h-40 rounded-lg" /> : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((project) => (
          <RecordActions key={project.id} kind="project" record={{...project,title:project.name,key:project.project_key}} onOpen={()=>openProject(project)}>{menu=><Card data-testid={`project-card-${project.id}`} tabIndex={0} className="min-w-0 cursor-pointer transition hover:border-primary/40 hover:shadow-md">
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{project.project_key}</p>
                  <h2 className="mt-1 truncate text-lg font-semibold"><button type="button" className="text-left hover:text-primary" onClick={()=>openProject(project)}>{project.name}</button></h2>
                </div>
                <div className="flex items-center gap-1"><Badge className={statusColor(project.status)}>{project.status}</Badge>{menu}</div>
              </div>
              <p className="mt-3 line-clamp-2 min-h-10 text-sm text-muted-foreground">{project.description || "No description added yet."}</p>
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

