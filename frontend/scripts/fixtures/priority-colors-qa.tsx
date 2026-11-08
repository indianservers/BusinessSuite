import React,{useState} from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import GridTable from "@/shared/data-grid/GridTable";
import {NativeSelect} from "@/components/ui/native-select";
import {useAuthStore} from "@/store/authStore";
import "@/index.css";
import "@/shared/priority/priority.css";
useAuthStore.setState({user:{id:1,role:"admin",is_superuser:true} as any,isAuthenticated:true});
const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
const levels=["Urgent","High","Medium","Low"];
function App(){const [low,setLow]=useState("Low");return <main style={{padding:24}}><h1>Shared priority colors</h1>
<section aria-label="Native records"><GridTable gridId="priority-native"><thead><tr><th>Name</th><th>Priority</th></tr></thead><tbody>{levels.map((priority,index)=><tr key={priority}><td><input aria-label={`Record ${index}`} value={`Record ${index}`} readOnly/></td><td><NativeSelect aria-label={`Priority ${index}`} value={index===3?low:priority} onChange={e=>setLow(e.target.value)}>{levels.map(level=><option key={level}>{level}</option>)}</NativeSelect></td></tr>)}</tbody></GridTable></section>
<section aria-label="Adapted records"><GridTable gridId="priority-adapted"><thead><tr><th>Name</th><th>Priority</th></tr></thead><tbody>{[...levels,"Normal","Critical",7].map((priority,index)=><tr key={index}><td>Adapted {index}</td><td>{priority}</td></tr>)}</tbody></GridTable></section>
<section aria-label="Record cards">{levels.map(priority=><article data-priority-row data-priority={priority} key={priority} style={{padding:12,margin:8}}><span data-priority-badge data-priority={priority}>{priority}</span> record</article>)}</section>
</main>}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><BrowserRouter><App/></BrowserRouter></QueryClientProvider>);
