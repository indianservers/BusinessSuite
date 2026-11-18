import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ModuleDashboardPage from "@/pages/ModuleDashboardPage";
import { useAuthStore } from "@/store/authStore";
import "@/index.css";
const access = { managed: false, companyId: 1, companyName: "QA Workspace", memberships: [1,2], organizations: [{id:1,name:"QA Workspace"},{id:2,name:"Second workspace"}], grants: {}, modules: [], isAccessAdmin: true, isGlobalAdmin: true };
useAuthStore.setState({ isAuthenticated: true, isHydrated: true, accessToken: "qa-fixture", user: { id: 9001, email: "launcher@example.test", role: "admin", is_superuser: true, access } });
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><ModuleDashboardPage/></BrowserRouter></QueryClientProvider>);
