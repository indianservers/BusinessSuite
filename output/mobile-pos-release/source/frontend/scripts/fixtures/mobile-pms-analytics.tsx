import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter,Routes,Route,useLocation} from "react-router-dom";
import {QueryClient,QueryClientProvider,onlineManager} from "@tanstack/react-query";
import Page from "@/apps/project-management/pages/AnalyticsPage";
import {useAuthStore} from "@/store/authStore";
import "@/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:1,email:"qa@example.test",role:"admin",is_superuser:true}});
onlineManager.setOnline(!new URLSearchParams(location.search).has("offline"));
Object.assign(window,{__analyticsOnline:(online:boolean)=>onlineManager.setOnline(online)});
const view=new URLSearchParams(location.search).get("view")||"team";
const initial=(view==="scoped"?"/pms/projects/86/analytics":view==="project"?"/pms/analytics/projects":"/pms/analytics/team")+"?start=2026-11-01&end=2026-11-10"+(new URLSearchParams(location.search).has("seed")?"&workspace=1&project=86&team=10&member=1":"");
function Probe(){const route=useLocation();Object.assign(window,{__analyticsLocation:route.pathname+route.search+route.hash});return null;}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[initial]}><Probe/><Routes><Route path="/pms/analytics/team" element={<Page mode="team"/>}/><Route path="/pms/analytics/projects" element={<Page mode="project"/>}/><Route path="/pms/projects/:projectId/analytics" element={<Page mode="project"/>}/><Route path="*" element={<p>Linked record destination</p>}/></Routes></MemoryRouter></QueryClientProvider>);
