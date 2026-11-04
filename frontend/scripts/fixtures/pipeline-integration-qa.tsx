import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import EnterpriseDealsPage from "@/apps/crm/deals/EnterpriseDealsPage";
import KanbanBoard from "@/apps/project-management/pages/KanbanBoard";
import RecruitmentPage from "@/apps/hrms/pages/recruitment/RecruitmentPage";
import SRMWorkspacePage from "@/apps/srm/pages/SRMWorkspacePage";
import { useAuthStore } from "@/store/authStore";
useAuthStore.setState({user:{id:1,email:"pipeline-qa@example.test",is_superuser:true,role:"admin"},isAuthenticated:true,isHydrated:true,accessToken:"fixture"});
const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
export default function Integration(){const module=new URLSearchParams(location.search).get("integration");return <QueryClientProvider client={client}><MemoryRouter initialEntries={[module==="pms"?"/pms/projects/1/board":"/qa"]}><Routes><Route path="/pms/projects/:projectId/board" element={<KanbanBoard/>}/><Route path="/qa" element={module==="crm"?<EnterpriseDealsPage initialView="kanban"/>:module==="hrms"?<RecruitmentPage/>:<SRMWorkspacePage kind="salesOrders"/>}/></Routes></MemoryRouter></QueryClientProvider>;}
