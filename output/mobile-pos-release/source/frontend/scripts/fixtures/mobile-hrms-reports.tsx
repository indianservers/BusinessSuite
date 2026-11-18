import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import ReportsPage from "../../src/apps/hrms/pages/reports/ReportsPage";
import {useAuthStore} from "../../src/store/authStore";
import "../../src/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:12,email:'hr-reports@example.test',role:'employee',is_superuser:false}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/hrms/reports']}><main style={{padding:12}}><ReportsPage/></main></MemoryRouter></QueryClientProvider>);
