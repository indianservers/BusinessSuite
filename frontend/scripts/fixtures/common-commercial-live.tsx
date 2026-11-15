import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Link, useNavigate, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CommonEntityPage from "@/common/CommonEntityPage";
import { crmRoutes } from "@/apps/crm/routes";
import { srmRoutes } from "@/apps/srm/routes";
import { getRoleNav } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/services/api";
import { Toaster } from "@/components/ui/toaster";
import "../../src/index.css";

const harness = window as typeof window & {qaAuth:{token:string;branch:string};qaApi:typeof api;qaNavigate:ReturnType<typeof useNavigate>};
sessionStorage.setItem("suite-organization", "1");
sessionStorage.setItem("suite-branch", harness.qaAuth.branch);
useAuthStore.setState({isHydrated:false,isAuthenticated:true,accessToken:harness.qaAuth.token,user:null});
harness.qaApi = api;
const routes = [...crmRoutes, ...srmRoutes];
function Harness() {
  harness.qaNavigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore(state => state.user);
  const nav = getRoleNav(user?.role, user?.is_superuser, location.pathname + location.search).filter(item => item.group === "Commercial documents");
  return <><nav aria-label="Commercial documents">{nav.map(item => <Link className="mr-3" key={item.to} to={item.to}>{item.label}</Link>)}</nav><Routes><Route path="common/:entity/*" element={<CommonEntityPage routes={routes}/>}/><Route path="*" element={<h1>Module home</h1>}/></Routes></>;
}
async function mount() {
  const [identity, access] = await Promise.all([api.get("/auth/me",{recordCache:false}),api.get("/access/me",{recordCache:false})]);
  const role = typeof identity.data.role === "string" ? identity.data.role : identity.data.role?.name;
  useAuthStore.setState({isHydrated:true,user:{...identity.data,role,primary_role:role,access:access.data}});
  createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><React.Suspense fallback={<p role="status">Loading manager…</p>}><Harness/><Toaster/></React.Suspense></BrowserRouter></QueryClientProvider>);
}
void mount();
