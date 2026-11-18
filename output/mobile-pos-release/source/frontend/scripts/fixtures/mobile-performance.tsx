import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import PerformancePage from '@/apps/hrms/pages/performance/PerformancePage';import{useAuthStore}from'@/store/authStore';import{Toaster}from'@/components/ui/toaster';import '@/index.css';
const viewer=location.search.includes('viewer');useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:1,employee_id:2,role:'employee',is_superuser:false,access:{managed:true,companyId:1,companyName:'QA company',memberships:[1],organizations:[],modules:[],grants:{hrms:{enabled:true,role:'employee',scope:'company',permissions:['performance_view'],actions:viewer?[]:['create','edit','delete']}}}}});
const performanceQaClient=new QueryClient({defaultOptions:{queries:{retry:false}}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={performanceQaClient}><MemoryRouter initialEntries={['/hrms/performance']}><main style={{padding:12}}><PerformancePage/></main><Toaster/></MemoryRouter></QueryClientProvider>);

(window as unknown as {switchPerformanceUser:(id:number,companyId?:number)=>void}).switchPerformanceUser=(id,companyId=1)=>useAuthStore.setState(state=>({accessToken:`fixture-${id}`,user:state.user?{...state.user,id,access:state.user.access?{...state.user.access,companyId}:undefined}:state.user}));

(window as unknown as {refreshCalibration:()=>Promise<void>}).refreshCalibration=()=>performanceQaClient.invalidateQueries({queryKey:["perf-calibration"]});
