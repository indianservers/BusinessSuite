import { useState } from "react";
import { platformApi as api } from "@/services/platform-api";
import { useData, useOwner, allowed, Loading, Alert, Table, Badge, message, type Data } from "./shared";

export default function Databases() {
  const { me } = useOwner();
  const rows = useData<Data[]>("/platform/databases");
  const servers = useData<Data[]>("/platform/database-servers");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  if (!allowed(me,"settings.manage")) return <Alert error="Company database management is restricted to platform owners."/>;
  return <><header className="po-heading"><div><h1>Company databases</h1><p>One approved company, one PostgreSQL database. Routing records remain in the separate Indian Servers Platform Owner database.</p></div><button onClick={()=>{rows.refresh();servers.refresh();}}>Refresh databases</button></header>
    <Alert error={error}/>{notice&&<div role="status" className="po-notice">{notice}</div>}
    <section className="po-panel"><h2>Database servers</h2><Loading busy={servers.busy} error={servers.error}/><Table rows={servers.data||[]} columns={[
      {label:"Server",render:r=><>{r.name}<small>{r.host}:{r.port}</small></>},
      {label:"Placement",render:r=><>{r.database_count} / {r.max_databases} databases<small>{r.active?"Accepting new companies":"Placement paused"}</small></>}
    ]}/><small>Placement capacity is configurable. Database connections open on demand; idle companies do not reserve connection pools.</small></section>
    <section className="po-panel"><h2>Company database directory</h2><Loading busy={rows.busy} error={rows.error}/><Table rows={rows.data||[]} columns={[
      {label:"Company",render:r=><>{r.company_name}<small>{r.workspace_code}</small></>},
      {label:"Database",render:r=><>{r.database_name}<small>{r.server_name} · routing version {r.routing_version}</small></>},
      {label:"State",render:r=><><Badge>{r.status}</Badge><small>{r.last_error||r.schema_version}</small></>},
      {label:"Actions",render:r=><div className="po-actions"><a href={r.login_url} target="_blank" rel="noreferrer">Company login</a><button disabled={r.status!=="ready"} onClick={async()=>{try{const {data}=await api.post(`/platform/databases/${r.id}/check`);setNotice(`${r.workspace_code}: healthy · ${data.company_count} company · ${data.database_name}`);setError("");}catch(e){setError(message(e));}}}>Check database</button></div>}
    ]}/></section><p className="po-muted">Existing shared customers require an explicit data migration. Credentials are never displayed. Moving a database requires a maintenance window, verified copy and directory cutover.</p></>;
}
