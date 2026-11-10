import React,{useMemo,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import LocalRecordGrid from '@/shared/data-grid/LocalRecordGrid';
import SharedDataGrid from '@/shared/data-grid/SharedDataGrid';
import {localGridSource} from '@/shared/data-grid/local-source';
import {SmartCreateModal} from '@/shared/creation/SmartCreateModal';
import {useAuthStore} from '@/store/authStore';
import type {GridColumn,GridDataSource} from '@/shared/data-grid/types';
import '@/index.css';
type Row={id:string;name:string;status:string};
const columns:GridColumn<Row>[]=[{id:'name',title:'Name'},{id:'status',title:'Status',type:'status'}];
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.invalid',role:'super_admin',is_superuser:true}});
function Fixture(){const rows=useRef<Row[]>([{id:'17',name:'Original QA',status:'Active'}]);const[refresh,setRefresh]=useState(0),[editing,setEditing]=useState(false),[name,setName]=useState('');const source=useMemo<GridDataSource<Row>>(()=>({key:'stable-edit-source',load:async(q,s)=>localGridSource('stable-edit-source',rows.current,columns,r=>r.id).load(q,s)}),[]);return <main>{new URLSearchParams(location.search).has('local')?<LocalRecordGrid gridId="edit-refresh" title="QA records" columns={columns} rows={rows.current} getRowId={r=>r.id} initialQuery={{grouping:['status']}} refreshKey={refresh} rowActions={[{id:'edit',label:'Edit',quick:true,run:r=>{setName(r.name);setEditing(true)}}]}/>:<SharedDataGrid gridId="edit-refresh" title="QA records" columns={columns} dataSource={source} getRowId={r=>r.id} initialQuery={{grouping:['status']}} refreshKey={refresh} rowActions={[{id:'edit',label:'Edit',quick:true,run:r=>{setName(r.name);setEditing(true)}}]}/>}{editing&&<SmartCreateModal definition={{entity:'record',title:'Edit QA record',mode:'edit',presentation:'page',size:'compact'}} onClose={()=>setEditing(false)}><form onSubmit={e=>{e.preventDefault();rows.current=rows.current.map(r=>({...r,name}));setRefresh(v=>v+1);setEditing(false)}}><label>Name<input value={name} onChange={e=>setName(e.target.value)}/></label><button type="submit" data-save-action>Save changes</button></form></SmartCreateModal>}</main>}
createRoot(document.getElementById('root')!).render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><Fixture/></QueryClientProvider></MemoryRouter>);
