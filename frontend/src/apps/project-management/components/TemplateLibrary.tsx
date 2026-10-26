import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { useState } from "react";
import { Layers, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Template = {
  id: number;
  name: string;
  description: string;
  project_id: number;
  task_titles: string[];
  enabled: boolean;
};

export default function TemplateLibrary<T extends Template>({ templates, projects, canEdit, busy, onPreview }: {
  templates: T[];
  projects: { id: number; name: string }[];
  canEdit: boolean;
  busy: boolean;
  onPreview: (template: T) => void;
}) {
  const [search, setSearch] = useState("");
  const [project, setProject] = useState("");
  const [size, setSize] = useState("");
  const [availability, setAvailability] = useState("active");
  const visible = templates.filter(template => {
    const projectName = projects.find(item => item.id === template.project_id)?.name || "";
    const matchesSearch = [template.name, template.description, projectName, ...template.task_titles].join(" ").toLowerCase().includes(search.trim().toLowerCase());
    return matchesSearch && (!project || template.project_id === Number(project))
      && (!size || (size === "small" ? template.task_titles.length <= 5 : template.task_titles.length > 5))
      && (availability === "all" || template.enabled);
  });
  const selectClass = "h-11 min-w-0 rounded-md border bg-background px-3 text-sm";

  return <section aria-label="Workspace template library" className="space-y-5">
    <div className="rounded-xl border bg-primary/5 p-5">
      <div className="flex items-center gap-3"><Layers className="h-6 w-6 text-primary" /><h3 className="text-xl font-semibold">Template center</h3></div>
      <p className="mt-2 text-sm text-muted-foreground">Reuse your team's proven workflows. Preview the tasks and destination before creating work.</p>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[2fr_1fr_1fr_1fr]">
      <div className="relative"><Search aria-hidden="true" className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" /><Input aria-label="Search templates" placeholder="Search names, descriptions or tasks…" value={search} onChange={event => setSearch(event.target.value)} className="h-11 pl-9" /></div>
      <select aria-label="Filter templates by project" className={selectClass} value={project} onChange={event => setProject(event.target.value)}><option value="">All projects</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <select aria-label="Filter templates by task count" className={selectClass} value={size} onChange={event => setSize(event.target.value)}><option value="">Any task count</option><option value="small">Up to 5 tasks</option><option value="large">6 or more tasks</option></select>
      <select aria-label="Template availability" className={selectClass} value={availability} onChange={event => setAvailability(event.target.value)}><option value="active">Active templates</option><option value="all">Include paused</option></select>
    </div>
    <p role="status" className="text-sm text-muted-foreground">{visible.length} of {templates.length} workspace templates</p>
    {!visible.length && <div className="rounded-xl border border-dashed p-8 text-center"><h3 className="font-semibold">{templates.length ? "No matching templates" : "Your template library starts here"}</h3><p className="mt-2 text-sm text-muted-foreground">{templates.length ? "Try another search or clear the filters." : "Owners and admins can save a reusable set of tasks using Create template."}</p>{!!templates.length && <Button className="mt-4" variant="outline" onClick={() => { setSearch(""); setProject(""); setSize(""); setAvailability("all"); }}>Clear filters</Button>}</div>}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {visible.map(template => <article key={template.id} className="flex min-w-0 flex-col overflow-hidden rounded-xl border bg-background transition-shadow hover:shadow-md">
        <div className="space-y-2 border-b bg-muted/30 p-4" aria-label={`${template.name} task preview`}>
          {template.task_titles.slice(0, 3).map((title, index) => <div key={index} className="flex items-center gap-2 text-xs"><span aria-hidden="true" className="h-3 w-3 shrink-0 rounded-sm border border-primary/40" /><span className="truncate">{title}</span></div>)}
          <p className="text-xs text-muted-foreground">{template.task_titles.length} tasks{template.task_titles.length > 3 ? ` · +${template.task_titles.length - 3} more in preview` : ""}</p>
        </div>
        <div className="flex flex-1 flex-col gap-3 p-4">
          <div><h3 className="break-words font-semibold">{template.name}</h3><p className="mt-1 break-words text-xs text-muted-foreground">{projects.find(item => item.id === template.project_id)?.name || "Project unavailable"} · {template.enabled ? "Active" : "Paused"}</p></div>
          <div className="line-clamp-3 break-words text-sm text-muted-foreground"><RichTextContent value={template.description || "A reusable task workflow for this project."}/></div>
          <Button className="mt-auto w-full" variant="outline" disabled={busy || !canEdit || !template.enabled} onClick={() => onPreview(template)}>Preview and use</Button>
        </div>
      </article>)}
    </div>
    {!canEdit && <p className="text-sm text-muted-foreground">Guests can browse templates. Workspace members can apply them.</p>}
  </section>;
}
