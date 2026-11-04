import { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Record360Workspace from "../../src/shared/records/Record360Workspace";
import TasksFollowUpsPage from "../../src/apps/project-management/pages/TasksFollowUpsPage";
import TaskRecordLinks from "../../src/shared/records/TaskRecordLinks";
import RecordQuickPreview, {openRecordPreview} from "../../src/components/RecordQuickPreview";
import "../../src/index.css";
const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});
function Fixture(){const [id,setId]=useState(1),[action,setAction]=useState("");return <main style={{padding:20}}><button onClick={()=>setId(id===1?2:1)}>Switch customer</button><output aria-label="Selected action">{action}</output><Record360Workspace key={id} kind="company" id={id} onAction={setAction} details={<p>Existing customer editor</p>}/></main>;}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={['/pms/tasks-follow-ups']} >{location.search.includes('preview')?<main><button onClick={()=>openRecordPreview({id:1,name:'Axiom Telecom'},'/crm/companies')}>Preview customer</button><RecordQuickPreview/></main>:location.search.includes('links')?<main style={{padding:20}}><TaskRecordLinks taskId={1}/></main>:location.search.includes('queue')?<TasksFollowUpsPage/>:<Fixture/>}</MemoryRouter></QueryClientProvider>);
