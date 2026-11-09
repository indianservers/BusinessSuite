import React from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter} from "react-router-dom";
import NoteCloudSave from "@/shared/productivity/NoteCloudSave";
import "@/index.css";
const source=new URLSearchParams(location.search).get("source")==="crm"?"crm":"project_management";
createRoot(document.getElementById("root")!).render(<BrowserRouter><main className="p-6"><h1>Original private note</h1><p>Original note remains editable here.</p><NoteCloudSave source={source} title="Private meeting" content="Original content" prepare={source==="project_management"?async()=>({id:7,version:5}):undefined}/></main></BrowserRouter>);
