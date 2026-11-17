import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {ProjectPicker,StaffPicker,ServicePicker} from '@/apps/srm/industry/IndustryOperationsPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';

useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.com',role:'admin',is_superuser:true}});
function Fixture(){
  const [project,setProject]=useState(''),[staff,setStaff]=useState(''),[service,setService]=useState('');
  return <main className="space-y-6 p-4">
    <section aria-label="Project test"><ProjectPicker value={project} change={setProject}/></section>
    <section aria-label="Staff test"><StaffPicker value={staff} change={setStaff}/></section>
    <section aria-label="Service test"><ServicePicker value={service} change={setService}/></section>
    <button onClick={()=>{setProject('');setStaff('');setService('');}}>Reset selections</button>
    <button onClick={()=>{setProject('2');setStaff('2');setService('2');}}>Replace selections</button>
  </main>;
}
createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/srm/construction']}><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><Fixture/></QueryClientProvider></MemoryRouter>);
