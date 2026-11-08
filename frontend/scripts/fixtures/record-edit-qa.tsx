import React from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider,useQuery} from '@tanstack/react-query';
import {BrowserRouter} from 'react-router-dom';
import RecordMaintenance from '../../src/components/RecordMaintenance';
import RecordDefinitionActions from '../../src/components/RecordDefinitionActions';
import {useAuthStore} from '../../src/store/authStore';
import {installRecordListRefresh} from '../../src/lib/record-changes';
import '../../src/index.css';
const definition=new URLSearchParams(location.search).has('definition');
const client=new QueryClient();installRecordListRefresh(client);
useAuthStore.setState({isAuthenticated:true,accessToken:`qa.${btoa(JSON.stringify({sid:'shared-editor-qa'}))}.signature`,user:{id:100,email:'qa@example.com',role:'admin',is_superuser:true,employee_id:null}});
function App(){
 const query=useQuery({queryKey:['qa-records'],initialData:{items:[{id:1,name:'First record'},{id:2,name:'Keep record'}],total:2},staleTime:Infinity,queryFn:async()=>(await (await fetch('/__qa_list')).json())});
 return <main><h1>Shared record list</h1><input aria-label="Keep filter" defaultValue="Active"/>{query.data.items.map(row=><article key={row.id}><span>{row.name}</span>{definition?<RecordDefinitionActions record={row} endpoint={`/analytics/reports/${row.id}`} queryKeys={['qa-records']} permissions={['analytics_manage']}/>:<RecordMaintenance record={row} name={row.name} endpoint={`/assets/${row.id}`} queryKeys={['qa-records']} fields={[{key:'name',label:'Record name',required:true}]} canEdit canDelete/>}</article>)}</main>;
}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><BrowserRouter><App/></BrowserRouter></QueryClientProvider>);
