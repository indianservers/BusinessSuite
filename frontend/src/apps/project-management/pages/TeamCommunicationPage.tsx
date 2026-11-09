import { Button } from "@/components/ui/button";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { MessageCircle } from "lucide-react";
import { useCommunicationScope } from "@/shared/communication/scope";
import { projectsAPI } from "../services/api";
import ProjectCommunicationPage from "./ProjectCommunicationPage";
import { workspaceError } from "./workspaceTypes";

export default function TeamCommunicationPage() {
  const scope = useCommunicationScope();
  const [params, setParams] = useSearchParams();
  const projects = useInfiniteQuery({
    queryKey: ["team-communication-projects", scope],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => projectsAPI.list(pageParam, 100),
    getNextPageParam: (last, pages) => last.length === 100 ? pages.length * 100 : undefined,
  });
  const rows = projects.data?.pages.flat() || [];
  const requested = Number(params.get("project"));
  const id = Number.isInteger(requested) && requested > 0 ? requested : rows[0]?.id;
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4">
      <label htmlFor="team-communication-project" className="text-sm font-medium">Project conversation</label>
      <select id="team-communication-project" className="min-w-0 max-w-full rounded-md border bg-background px-3 py-2 text-sm" disabled={projects.isPending || !rows.length} value={id || ""} onChange={e => { const next = new URLSearchParams(params); next.set("project", e.target.value); setParams(next); }}>
        {!rows.length && <option value="">{projects.isPending ? "Loading projects…" : "No projects available"}</option>}
        {!!id && !rows.some(p => p.id === id) && <option value={id}>Selected project</option>}
        {rows.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select>
      {projects.hasNextPage && <button className="text-sm underline" disabled={projects.isFetchingNextPage} onClick={() => void projects.fetchNextPage()}>{projects.isFetchingNextPage ? "Loading…" : "Load more projects"}</button>}
    </div>
    {projects.isError && <p role="alert">{workspaceError(projects.error)} <Button type="submit" variant="outline" className="underline" onClick={() => void projects.refetch()}>Retry</Button></p>}
    {id ? <ProjectCommunicationPage key={`${scope}:${id}`} selectedProjectId={id} /> : !projects.isPending && !projects.isError ? <div className="rounded-xl border bg-card p-10 text-center"><MessageCircle className="mx-auto mb-3 text-emerald-600" /><h1 className="text-xl font-semibold">Team communication</h1><p className="mt-2 text-sm text-muted-foreground">Your project conversations will appear here when you have access to a project.</p></div> : null}
  </div>;
}
