import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter,Routes,Route,useLocation} from "react-router-dom";
import Page from "@/apps/project-management/pages/PlansPage";
import {capabilityTiers} from "@/apps/project-management/capabilities";
import "@/index.css";
Object.assign(window,{__planCatalogue:capabilityTiers});
function Destination(){return <p>Tool destination: {useLocation().pathname}</p>}
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/pms/plans"]}><Routes><Route path="/pms/plans" element={<Page/>}/><Route path="*" element={<Destination/>}/></Routes></MemoryRouter>);
