import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import ImportWorkspace from "@/shared/data-transfer/ImportWorkspace";
import {useAuthStore} from "@/store/authStore";
import "@/index.css";
const module=new URLSearchParams(location.search).get("module")||"crm";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"isolated-fixture",user:{id:1,email:"qa@example.com",role:"admin",is_superuser:true}});
createRoot(document.getElementById("root")!).render(<MemoryRouter><ImportWorkspace module={module}/></MemoryRouter>);
