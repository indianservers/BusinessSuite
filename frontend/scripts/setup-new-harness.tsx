import React from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter} from "react-router-dom";
import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import SetupReadiness from "../src/components/suite/SetupReadiness";
import ModuleNewMenu from "../src/components/app/ModuleNewMenu";
import CRMRecordsPage from "../src/apps/crm/CRMRecordsPage";
import CompanyAdminPage from "../src/pages/CompanyAdminPage";
import {useAuthStore} from "../src/store/authStore";
import {categorizeNavigation} from "../src/lib/navigation-categories";
import "../src/index.css";

useAuthStore.setState({isAuthenticated:true,user:{id:1,email:"qa@example.com",role:"admin",is_superuser:true}});
function Harness(){return location.pathname==="/crm/records" ? <CRMRecordsPage/> : location.pathname==="/company-admin" ? <CompanyAdminPage/> : <><ModuleNewMenu/><SetupReadiness/><SetupReadiness embedded/><output aria-label="Potential clients category">{categorizeNavigation([{to:"/crm/potential-clients",group:"Core"}],"crm")[0].group}</output></>;}
createRoot(document.getElementById("root")!).render(<BrowserRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><Harness/></QueryClientProvider></BrowserRouter>);
