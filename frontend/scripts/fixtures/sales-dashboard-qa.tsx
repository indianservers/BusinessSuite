import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SalesDashboard from "@/apps/srm/pages/SalesDashboard";
import { useAuthStore } from "@/store/authStore";
import "@/index.css";
const readonly=new URLSearchParams(location.search).has("readonly");
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"sales-qa",user:{id:9001,email:"sales@example.test",role:readonly?"srm_viewer":"srm_admin",is_superuser:!readonly,access:{managed:false,companyId:1,memberships:[1],grants:{},modules:[],isAccessAdmin:!readonly,isGlobalAdmin:!readonly}}});
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><SalesDashboard/></BrowserRouter></QueryClientProvider>);
