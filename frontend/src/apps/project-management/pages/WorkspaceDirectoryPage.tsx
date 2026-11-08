import { useSearchParams } from "react-router-dom";
import WorkspacesPage from "./WorkspacesPage";
import ProjectWorkspaceDirectory from "./ProjectWorkspaceDirectory";
export default function WorkspaceDirectoryPage() {
  const [params] = useSearchParams();
  return ["workspace", "new", "task", "invite"].some(key => params.has(key)) ? <WorkspacesPage /> : <ProjectWorkspaceDirectory />;
}
