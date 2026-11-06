import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, MessageCircle } from "lucide-react";
import { projectsAPI, tasksAPI } from "../services/api";
import ProjectCommunication from "../components/ProjectCommunication";
import { workspaceError } from "./workspaceTypes";
import { useCommunicationScope } from "@/shared/communication/scope";

/** Communication-only page; project CRUD stays in the existing project screens. */
export default function ProjectCommunicationPage({ selectedProjectId }: { selectedProjectId?: number } = {}) {
  const { projectId } = useParams<{ projectId: string }>();
  const scope = useCommunicationScope();
  const id = selectedProjectId ?? Number(projectId);
  const project = useQuery({ queryKey: ["project-communication-details", scope, id], enabled: Number.isInteger(id) && id > 0, queryFn: () => projectsAPI.get(id) });
  const tasks = useQuery({ queryKey: ["project-communication-tasks", scope, id], enabled: !!project.data, queryFn: () => tasksAPI.list(id) });
  if (!Number.isInteger(id) || id <= 0) return <p role="alert">Choose a valid project.</p>;
  if (project.isPending) return <p role="status">Loading project communication…</p>;
  if (project.isError) return <div role="alert" className="space-y-3 rounded-xl border p-6"><p>{workspaceError(project.error)}</p><button className="underline" onClick={() => void project.refetch()}>Retry</button></div>;
  return <div className="space-y-5">
    <Link to={`/pms/projects/${id}`} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft size={16} />Back to project</Link>
    <header><h1 className="page-title flex items-center gap-2"><MessageCircle className="text-emerald-600" size={24} />Team communication</h1><p className="page-description">{project.data.name}</p></header>
    {tasks.isError && <p role="alert" className="text-sm text-destructive">Task sharing is unavailable. <button className="underline" onClick={() => void tasks.refetch()}>Retry</button></p>}
    <ProjectCommunication project={project.data} tasks={tasks.data || []} />
  </div>;
}
