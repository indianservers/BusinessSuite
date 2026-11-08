import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import GridTable from "@/shared/data-grid/GridTable";
import { useAuthStore } from "@/store/authStore";
import "@/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,email:"qa@example.test",role:"admin",is_superuser:true}});
const rows=[
 {id:1,name:"Onboard Alex",status:"In progress",start_date:"2026-11-01",expected_completion_date:"2026-11-15",progress_percent:50},
 {id:2,name:"Onboard Bea",status:"Completed",start_date:"2026-11-01",expected_completion_date:"2026-11-08",progress_percent:100},
 {id:3,name:"Invalid schedule",status:"In progress",start_date:"2026-11-20",expected_completion_date:"2026-11-01",progress_percent:0},
];
function Fixture(){const navigate=useNavigate();const [items,setItems]=useState(rows);const [completed,setCompleted]=useState(false);return <main style={{padding:24,maxWidth:1200,margin:"auto"}}><h1>Collection rollout verification</h1><button onClick={()=>navigate("/hrms/exit")}>Go to exit collection</button><button onClick={()=>navigate("/hrms/onboarding")}>Go to onboarding collection</button><GroupedRecords scope="hrms-onboarding-qa" items={items} fields={[{id:"status",label:"Status",value:row=>row.status}]} gridClassName="grid gap-3 md:grid-cols-2" renderItem={row=><article><h2>{row.name}</h2><p data-qa-preview-status>{row.status}</p><button onClick={()=>setItems(current=>current.map(item=>item.id===row.id?{...item,status:"Updated"}:item))}>Update record status</button><button onClick={()=>setItems(current=>current.filter(item=>item.id!==row.id))}>Remove record</button><button onClick={()=>setCompleted(true)}>{completed?"Original action completed":"Original permission-aware action"}</button></article>}/><h2>Adapted collection</h2><GridTable gridId="collection-rollout-adapter"><thead><tr><th>Contract</th><th>Status</th><th>Start date</th><th>End date</th><th>Progress</th></tr></thead><tbody>{rows.slice(0,2).map(row=><tr key={row.id}><td>{row.name}</td><td>{row.status}</td><td data-grid-value={row.start_date}>{row.start_date}</td><td data-grid-value={row.expected_completion_date}>{row.expected_completion_date}</td><td>{row.progress_percent}%</td></tr>)}</tbody></GridTable><h2>Editable collection regression fixture</h2><GridTable gridId="native-regression"><thead><tr><th><input type="checkbox" aria-label="Select fixture records"/></th><th style={{width:96}}>Name</th><th>Status</th><th>Progress</th></tr></thead><tbody><tr key="native-1"><td><input type="checkbox" aria-label="Select editable fixture"/></td><td>Editable record</td><td><input value="Active" readOnly aria-label="Fixture status"/></td><td>50%</td></tr></tbody></GridTable></main>;}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/hrms/onboarding"]}><Fixture/></MemoryRouter></QueryClientProvider>);
