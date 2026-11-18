import React, {useState} from "react";
import {createRoot} from "react-dom/client";
import {SmartCreateModal} from "@/shared/creation/SmartCreateModal";
import {guardTaskEnter} from "@/shared/creation/task-keyboard";
import "@/index.css";
function Fixture(){
 const [open,setOpen]=useState(true),[saved,setSaved]=useState(0);
 return <><output aria-label="Tasks saved">{saved}</output>{open?<SmartCreateModal definition={{entity:"task",title:"Create Task",presentation:"page",size:"large"}} onClose={()=>setOpen(false)}>
  <form onKeyDown={guardTaskEnter} onSubmit={event=>{event.preventDefault();setSaved(n=>n+1);setOpen(false);}}>
   <label>Task heading<input aria-label="Task heading" required/></label>
   <label>Description<textarea aria-label="Description"/></label>
   <div aria-label="Rich description" role="textbox" contentEditable suppressContentEditableWarning/>
   <button data-save-action type="submit">Create Task</button>
  </form>
 </SmartCreateModal>:<p>Task window closed</p>}</>;
}
createRoot(document.getElementById("root")!).render(<Fixture/>);
