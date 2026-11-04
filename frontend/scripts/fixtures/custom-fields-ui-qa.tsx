import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import CustomFieldsManager from "../../src/apps/crm/CustomFieldsManager";
import FieldControl, { fieldShown } from "../../src/shared/custom-fields/FieldControl";
import "../../src/index.css";
function Controls(){
 const [values,setValues]=useState<Record<string,unknown>>({number:0,checkbox:false});
 const fields=[{name:"Reference",field_type:"text"},{name:"Service",field_type:"radio",options:["Audit","Tax"]},{name:"Region",field_type:"combobox",options:["Hyderabad","Bengaluru","Chennai"]},{name:"Interests",field_type:"multi_select",options:["Audit","Tax","Advisory"]},{name:"Amount",field_type:"number"},{name:"Approved",field_type:"checkbox"}];
 return <main className="mx-auto max-w-3xl space-y-5 p-6"><h1 className="text-xl font-semibold">Custom field controls</h1>{fields.map(f=><section key={f.field_type} className="space-y-2"><h2 className="text-sm font-medium">{f.name}</h2><FieldControl field={f} value={values[f.field_type]} onChange={v=>setValues(current=>({...current,[f.field_type]:v}))}/></section>)}<output aria-label="Saved values">{JSON.stringify(values)}</output><p data-testid="placement">{String(fieldShown({options:{values:[],ui:{places:["create"]}}},"detail"))}</p></main>;
}
createRoot(document.getElementById("root")!).render(<BrowserRouter>{location.search.includes("controls")?<Controls/>:<div className="mx-auto max-w-6xl p-6"><CustomFieldsManager/></div>}</BrowserRouter>);
