import { useSearchParams } from "react-router-dom";
import WorkspacesPage from "./WorkspacesPage";
import ProjectWorkspaceDirectory from "./ProjectWorkspaceDirectory";
import {hasPmsWorkspaceShell} from "@/lib/task-workspace";
export default function WorkspaceDirectoryPage() {
  const [params] = useSearchParams();
  return hasPmsWorkspaceShell("/pms/workspaces",params.toString()) ? <WorkspacesPage /> : <ProjectWorkspaceDirectory />;
}
