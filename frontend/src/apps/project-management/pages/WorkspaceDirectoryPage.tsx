import { useSearchParams } from "react-router-dom";
import WorkspacesPage from "./WorkspacesPage";
import ProjectWorkspaceDirectory from "./ProjectWorkspaceDirectory";
export default function WorkspaceDirectoryPage() {
  const [params] = useSearchParams();
  return (["workspace", "task", "invite"].some(key => params.has(key)) || params.has("new") && params.get("new") !== "workspace") ? <WorkspacesPage /> : <ProjectWorkspaceDirectory />;
}
