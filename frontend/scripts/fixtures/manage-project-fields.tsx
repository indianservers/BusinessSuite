import React,{useState} from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {SmartCreateModal} from "@/shared/creation/SmartCreateModal";
import {CustomFieldsForm,type FieldDraft} from "@/apps/project-management/components/CustomFields";
import {useAuthStore} from "@/store/authStore";
import "@/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:1,email:"qa@example.invalid",role:"admin",is_superuser:true}});
function Fixture(){const [name,setName]=useState(""),[key,setKey]=useState("QA01"),[fields,setFields]=useState<FieldDraft>({});const entity=location.search.includes('task')?'task':'project';return <SmartCreateModal definition={{entity,title:`Create ${entity}`,presentation:"page",size:"large"}} onClose={()=>{}}><form onSubmit={e=>{e.preventDefault();throw Error('Managing fields must not submit the record');}}><label>Record name<input aria-label="Record name" value={name} onChange={e=>setName(e.target.value)}/></label><label>Record key<input aria-label="Record key" value={key} onChange={e=>setKey(e.target.value)}/></label><CustomFieldsForm entity={entity} values={fields} onChange={setFields}/><button type="submit" data-save-action>Create {entity}</button></form></SmartCreateModal>}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><Fixture/></MemoryRouter></QueryClientProvider>);
