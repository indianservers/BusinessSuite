import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import ReportsPage from "../../src/apps/project-management/pages/ReportsPage";
import {useAuthStore} from "../../src/store/authStore";
import "../../src/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:12,email:'reports@example.test',role:'admin',is_superuser:true}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><main style={{padding:12}}><ReportsPage/></main></MemoryRouter></QueryClientProvider>);
