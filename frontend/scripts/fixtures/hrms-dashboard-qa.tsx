import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "@/apps/hrms/pages/dashboard/DashboardPage";
import { useAuthStore } from "@/store/authStore";
import "@/index.css";
const personal = new URLSearchParams(location.search).get("actor") === "employee";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"dashboard-qa",user:{id:9001,email:"dashboard@example.test",employee_id:1,role:personal?"employee":"admin",is_superuser:!personal,access:{managed:false,companyId:1,companyName:"Dashboard QA",memberships:[1],grants:{},modules:[],isAccessAdmin:!personal,isGlobalAdmin:!personal}}});
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><DashboardPage/></BrowserRouter></QueryClientProvider>);
