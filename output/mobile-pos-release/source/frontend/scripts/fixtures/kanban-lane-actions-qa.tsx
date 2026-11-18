import { useState } from "react";
import { createRoot } from "react-dom/client";
import { DndContext } from "@dnd-kit/core";
import KanbanColumn from "../../src/apps/project-management/components/KanbanColumn";
import "../../src/index.css";
function Harness(){const [added,setAdded]=useState(0),[refreshed,setRefreshed]=useState(0),[readOnly,setReadOnly]=useState(false);return <><label><input type="checkbox" checked={readOnly} onChange={event=>setReadOnly(event.target.checked)}/>Read only</label><output aria-label="Added tasks">{added}</output><output aria-label="Refreshes">{refreshed}</output><DndContext><KanbanColumn column={{id:1,board_id:1,name:"Ready",status_key:"TODO",position:0,is_collapsed:false,task_count:0}} tasks={[]} readOnly={readOnly} onAddTask={()=>setAdded(value=>value+1)} onChanged={async()=>setRefreshed(value=>value+1)}/></DndContext></>}
createRoot(document.getElementById("root")!).render(<Harness/>);
