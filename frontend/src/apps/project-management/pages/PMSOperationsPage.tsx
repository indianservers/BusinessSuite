import { lazy } from "react";
const GanttPage=lazy(()=>import("./GanttPage"));
const WorkloadPage=lazy(()=>import("./WorkloadPage"));
const BacklogPage=lazy(()=>import("./BacklogPage"));
const RisksPage=lazy(()=>import("./RisksPage"));
import ProjectFinancials from "./ProjectFinancials";

type PMSOpsMode = "dependencies" | "resources" | "agile" | "financials" | "risk";
/** Legacy navigation aliases now render the real, permission-aware workspaces. */
export default function PMSOperationsPage({mode}:{mode:PMSOpsMode}) {
  if(mode==="dependencies")return <GanttPage/>;
  if(mode==="resources")return <WorkloadPage/>;
  if(mode==="agile")return <BacklogPage/>;
  if(mode==="risk")return <RisksPage/>;
  return <ProjectFinancials/>;
}
