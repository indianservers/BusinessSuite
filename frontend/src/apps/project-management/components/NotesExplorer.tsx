import NotesExplorer, { type NotesExplorerProps } from "@/shared/productivity/NotesExplorer";
import { tasksAPI } from "../services/api";
export default function PMSNotesExplorer(props: Omit<NotesExplorerProps,"loadProjectTasks"|"projectsLabel"|"personalLabel">) { return <NotesExplorer {...props} loadProjectTasks={tasksAPI.list}/>; }
