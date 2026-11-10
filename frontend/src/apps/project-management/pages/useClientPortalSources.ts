import {syncScope} from "@/shared/record-sync/store";
import { useRef, useState } from "react";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { filesAPI, milestonesAPI, projectsAPI } from "../services/api";
import type { PMSFileAsset, PMSMilestone, PMSProject } from "../types";
import { workspaceError } from "./workspaceTypes";

type Phase = "loading" | "ready" | "error";
type Kind = "milestones" | "files";

/** Independent mobile reads: a failed project must never masquerade as an empty result. */
export function useClientPortalSources(enabled: boolean) {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [milestones, setMilestones] = useState<PMSMilestone[]>([]);
  const [files, setFiles] = useState<PMSFileAsset[]>([]);
  const [phase, setPhase] = useState<Record<"projects" | Kind, Phase>>({projects:"loading", milestones:"loading", files:"loading"});
  const [errors, setErrors] = useState<Record<"projects" | Kind, string>>({projects:"", milestones:"", files:""});
  const ownerScope=useRef(syncScope());
  const epoch = useRef(0);
  const mutationRevision = useRef(0);
  const acknowledged = useRef(new Map<number, {revision:number; value:PMSMilestone}>());
  function commitMilestone(value:PMSMilestone) {
    if(ownerScope.current!==syncScope())return;
    acknowledged.current.set(value.id, {revision:++mutationRevision.current, value});
    setMilestones(rows => rows.map(row => row.id === value.id ? value : row));
  }
  const failed = useRef<Record<Kind, number[]>>({milestones:[], files:[]});
  const busy = useRef(new Set<string>());
  const retry = useRef<(kind: "projects" | Kind) => void>(() => {});

  useRefreshableEffect(() => {
    const version = ++epoch.current;
    if (!enabled) return;
    let active = true;
    const projectOrder = new Map<number, number>();
    const byProject = (a:{project_id?:number|null}, b:{project_id?:number|null}) => (projectOrder.get(a.project_id ?? -1) ?? 0) - (projectOrder.get(b.project_id ?? -1) ?? 0);
    const owns = () => active && epoch.current === version && ownerScope.current===syncScope();
    busy.current.clear();
    const mark = (kind: "projects" | Kind, status: Phase, error = "") => {
      if (!owns()) return;
      setPhase(value => ({...value, [kind]:status}));
      setErrors(value => ({...value, [kind]:error}));
    };
    async function children(kind: Kind, ids: number[]) {
      if (!owns() || busy.current.has(kind)) return;
      busy.current.add(kind);
      mark(kind, "loading");
      const results = await Promise.all(ids.map(async id => {
        try {
          if (kind === "milestones") {
            const startedRevision = mutationRevision.current;
            const rows = await milestonesAPI.list(id);
            if (owns()) setMilestones(values => [...values.filter(row => row.project_id !== id), ...rows.map(row => {
              const completed = acknowledged.current.get(row.id);
              // A read started before this acknowledgement cannot roll it back.
              // Never insert a row absent from the server's visible result.
              return completed && completed.revision > startedRevision ? completed.value : row;
            })].sort(byProject));
          } else {
            const rows = await filesAPI.list({project_id:id});
            if (owns()) setFiles(values => [...values.filter(row => row.project_id !== id), ...rows.filter(row => row.visibility === "Client Visible")].sort(byProject));
          }
          return {id, error:""};
        } catch (error) {
          // Withhold this project's prior rows after a failed access/read check.
          if (owns()) {
            if (kind === "milestones") setMilestones(values => values.filter(row => row.project_id !== id));
            else setFiles(values => values.filter(row => row.project_id !== id));
          }
          return {id, error:workspaceError(error)};
        }
      }));
      if (!owns()) return;
      busy.current.delete(kind);
      failed.current[kind] = results.filter(result => result.error).map(result => result.id);
      const messages = results.filter(result => result.error).map(result => `Project ${result.id}: ${result.error}`);
      mark(kind, messages.length ? "error" : "ready", messages.join("; "));
    }
    async function load() {
      if (!owns() || busy.current.has("projects")) return;
      busy.current.add("projects");
      mark("projects", "loading");
      mark("milestones", "loading");
      mark("files", "loading");
      setProjects([]); setMilestones([]); setFiles([]);
      try {
        const items = await projectsAPI.list();
        if (!owns()) return;
        const visible = items.filter(project => project.is_client_visible || project.status !== "Archived");
        visible.forEach((project, index) => projectOrder.set(project.id, index));
        setProjects(visible);
        mark("projects", "ready");
        await Promise.all([children("milestones", visible.map(project => project.id)), children("files", visible.map(project => project.id))]);
      } catch (error) {
        mark("projects", "error", workspaceError(error));
      } finally {
        if (owns()) busy.current.delete("projects");
      }
    }
    retry.current = kind => { if (kind === "projects") void load(); else void children(kind, failed.current[kind]); };
    void load();
    return () => { active = false; };
  }, [enabled]);
  return {projects, milestones, files, setMilestones, commitMilestone, phase, errors, retry:(kind: "projects" | Kind) => retry.current(kind)};
}
