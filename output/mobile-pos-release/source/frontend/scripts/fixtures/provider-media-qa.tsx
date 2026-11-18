/** Development-only settings fixture. No keys or provider calls. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import OperatorProviderSettings from '../../src/pages/ai-agents/OperatorProviderSettings';
import {api} from '../../src/services/api';
import {useAuthStore} from '../../src/store/authStore';
import '../../src/index.css';
if(!import.meta.env.DEV)throw Error('Development fixture only');
useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:7,email:'media-fixture@example.com',role:'Super Admin',is_superuser:true}});
let provider:any={provider:'gemini',model:'existing-text-model',enabled:true,data_sharing_allowed:true,has_key:true,
 max_tokens:3000,input_price:null,output_price:null,media:{image_enabled:false,image_model:'gemini-3.1-flash-image',transcription_enabled:false,transcription_model:'gemini-3.5-flash-lite'}};
const requests:any[]=[];(window as any).__mediaRequests=requests;
api.defaults.adapter=async config=>{
 const path=config.url||'',body=typeof config.data==='string'?JSON.parse(config.data):config.data;
 requests.push({path,method:config.method,body});let data:any={};
 if(path.endsWith('/project-management/workspaces'))data=[];
 else if(path.endsWith('/analytics'))data={groups:[],logs:[],server_plans:0,cost_note:'Synthetic unpriced usage.'};
 else if(config.method==='put'){provider={...provider,...body,has_key:true};data=provider}
 else if(path.endsWith('/providers'))data={items:[provider]};
 return {data,status:200,statusText:'OK',headers:{},config};
};
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/ai-agents/providers/gemini']}><main style={{padding:20}}><Routes><Route path="/ai-agents/providers/:provider" element={<OperatorProviderSettings/>}/></Routes></main></MemoryRouter></QueryClientProvider></React.StrictMode>);
