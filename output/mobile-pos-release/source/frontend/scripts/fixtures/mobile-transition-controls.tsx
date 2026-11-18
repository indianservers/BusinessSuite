import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import Page from '@/apps/project-management/components/TransitionApprovals';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,is_superuser:true,role:'admin'}});
function Harness(){const[task,setTask]=useState(91);Object.assign(window,{__task:setTask,__actor:()=>useAuthStore.setState({user:{id:2,is_superuser:true,role:'admin'}})});return <main style={{padding:12}}><Page taskId={task} registerLeaveGuard={guard=>{(window as any).__leave=guard;}} disabled={location.search.includes('disabled')} onChanged={()=>{(window as any).__changed=((window as any).__changed||0)+1}}/><a href="/controls-away" hidden={!location.search.includes('nav')}>Leave review</a><a href="#same" hidden={!location.search.includes('nav')}>Same page</a></main>}
createRoot(document.getElementById('root')!).render(<Harness/>);
