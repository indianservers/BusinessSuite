import { Navigate } from "react-router-dom";
import { sharedNotesPath } from "@/lib/shared-notes";

// Keep legacy imports working without mounting a separate local Notes store.
export default function CRMNotesWorkspace(_props: { legacyKey: string; onTasks: () => void; userId?: number }) {
  return <Navigate replace to={sharedNotesPath} />;
}
