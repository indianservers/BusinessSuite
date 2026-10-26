import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useState } from "react";
import { Link } from "react-router-dom";

export default function TaskViewPicker({ projectId }: { projectId?: number }) {
  const [search, setSearch] = useState("");
  const query = projectId ? `projectId=${projectId}&` : "";
  const views = [
    { name: "List", description: "Tasks grouped by status", url: `/pms/tasks?${query}layout=list` },
    { name: "Table", description: "Flat table with configurable columns", url: `/pms/tasks?${query}layout=table` },
    { name: "Gallery", description: "Task cards with selected properties", url: `/pms/tasks?${query}layout=gallery` },
    { name: "Board", description: projectId ? "Project Kanban with drag and drop" : "Choose a project to open its board", url: projectId ? `/pms/projects/${projectId}/board` : "/pms/projects" },
    { name: "Gantt / Timeline", description: "Project schedules and dependencies", url: projectId ? `/pms/projects/${projectId}/gantt` : "/pms/gantt" },
    { name: "Calendar", description: "Workspace tasks and milestones", url: "/pms/calendar" },
    { name: "Docs", description: "Workspace document library", url: "/pms/docs" },
    { name: "Dashboard", description: projectId ? "Project metrics and progress" : "Workspace portfolio", url: projectId ? `/pms/projects/${projectId}` : "/pms/dashboards" },
    { name: "Workload", description: "Workspace team capacity", url: "/pms/workload" },
    { name: "Forms", description: "Workspace intake forms", url: "/pms/forms" },
  ];
  const filtered = views.filter(view => `${view.name} ${view.description}`.toLowerCase().includes(search.toLowerCase()));
  return <nav aria-label="Task views" className="relative flex flex-wrap items-center gap-2 rounded-lg border bg-background p-3 text-sm">
    {views.slice(0, 4).map(view => <Link key={view.name} className="rounded px-3 py-2 hover:bg-muted focus-visible:ring-2" to={view.url}>{view.name}</Link>)}
    <details onKeyDown={event => { if (event.key === "Escape") { event.currentTarget.open = false; event.currentTarget.querySelector("summary")?.focus(); } }}>
      <summary aria-label="Choose task view" className="cursor-pointer rounded border px-3 py-2">+ View</summary>
      <div className="absolute left-0 top-full z-40 mt-2 w-full max-w-2xl rounded-xl border bg-background p-3 shadow-xl">
        <input aria-label="Search task views" placeholder="Search views" className="mb-3 w-full rounded border bg-background p-2" value={search} onChange={event => setSearch(event.target.value)} />
        <div className="grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2">{filtered.map(view => <Link key={view.name} to={view.url} onClick={event => { event.currentTarget.closest("details")?.removeAttribute("open"); }} className="rounded-lg border p-3 hover:bg-muted"><span className="font-medium">{view.name}</span><div className="mt-1 block text-xs text-muted-foreground"><RichTextContent value={view.description}/></div></Link>)}</div>
        {!filtered.length && <p className="p-3 text-muted-foreground">No matching view.</p>}
      </div>
    </details>
  </nav>;
}
