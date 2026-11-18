import type { QueryClient } from "@tanstack/react-query";
import type { GridQuery, GridResult } from "@/shared/data-grid/types";

/** Patch visible rows; insert new records only into an unfiltered first page. */
export function publishGridRecord<T extends { id: number | string }>(client: QueryClient, sourceKey: string, record: T) {
  for(const query of client.getQueryCache().getAll()) {
    if(query.queryKey[0]!=="shared-grid"||query.queryKey[2]!==sourceKey)continue;
    const view=query.queryKey[3] as GridQuery;
    client.setQueryData<GridResult<T>>(query.queryKey,current=>{
    if (!current) return current;
    const exists = current.rows.some(row => String(row.id) === String(record.id));
    const insert=view?.page===1&&!view.search&&!view.filters?.rules?.length&&!view.grouping?.length&&!view.path?.length&&!view.recordIds?.length&&!current.groups?.length;
    if(!exists&&!insert)return current;
    return { ...current, rows: exists ? current.rows.map(row => String(row.id) === String(record.id) ? {...row,...record} : row) : [record, ...current.rows].slice(0, current.pageSize), total: current.total + (exists ? 0 : 1), pageTotal: current.pageTotal + (exists ? 0 : 1) };
  });
  }
}

export function removeGridRecords(client: QueryClient, sourceKey: string, ids: (number | string)[]) {
  const removed=new Set(ids.map(String));
  client.setQueriesData<GridResult<{id:number|string}>>({predicate:query=>query.queryKey[0]==="shared-grid"&&query.queryKey[2]===sourceKey},current=>{
    if(!current)return current;
    const rows=current.rows.filter(row=>!removed.has(String(row.id))),count=current.rows.length-rows.length;
    return count?{...current,rows,total:Math.max(0,current.total-count),pageTotal:Math.max(0,current.pageTotal-count)}:current;
  });
}

export type RecordSaved = { url: string; method: string; record: Record<string, unknown>; resource?: string; ids?: (string|number)[]; operation?: "update"|"delete"|"restore"; patch?:Record<string,unknown>; kind?:string };
export const recordSavedEvent = "suite:record-saved";
const recordNamespaces=["crm","srm","fam","catalog","project-management","master-data","profiles","company","interns-hub","communication","analytics","customization","power-apps","attendance","recruitment","leave","timesheets","payroll","performance"];

/** Describe only a confirmed response; partial bulk failures remain visible. */
export function confirmedMutation(url:string,method:string,request:unknown,response:unknown):RecordSaved {
  method=method.toLowerCase();
  let body=request;
  if(typeof body==="string")try{body=JSON.parse(body);}catch{body={};}
  const input=(body&&typeof body==="object"?body:{}) as Record<string,any>;
  const record=(response&&typeof response==="object"?response:{}) as Record<string,any>;
  let resource=resourcePath(url);
  const suffix=resource.split("/").pop()||"";
  const action=String(input.action||input.operation||suffix).toLowerCase();
  const operation=method==="delete"||["delete","trash","archive","permanent"].includes(action)?"delete":["restore","unarchive"].includes(action)?"restore":"update";
  if(["bulk","trash","archive","delete","restore","unarchive","permanent"].includes(suffix))resource=resource.replace(/\/[^/]+$/,"");
  const identity=resource.match(/\/(\d+)$/)?.[1];
  if(identity)resource=resource.replace(/\/\d+$/,"");
  resource=resource.replace(/^\/master-data\/company-directory$/, "/master-data/companies");
  resource=resource.replace(/^\/crm\/deal-workspace\/grid$/, "/crm/deals");
  let ids:(number|string)[]=Array.isArray(record.successful_ids)?record.successful_ids:Array.isArray(record.deleted_ids)?record.deleted_ids:Array.isArray(record.archived_ids)?record.archived_ids:Array.isArray(input.ids)?input.ids:Array.isArray(input.task_ids)?input.task_ids:Array.isArray(input.records)?input.records.map((row:{id:number|string})=>row.id):identity?[identity]:[];
  if(Array.isArray(record.items)&&record.items.some(item=>typeof item.saved==="boolean"))ids=record.items.filter(item=>item.saved===true).map(item=>item.id);
  const failures=[...(Array.isArray(record.failed_ids)?record.failed_ids:[]),...(Array.isArray(record.errors)?record.errors:[]),...(Array.isArray(record.failed)?record.failed:[])];
  const identifiedFailures=failures.map(item=>item&&typeof item==="object"?item.id??item.record_id??item.task_id:typeof item==="number"||typeof item==="string"&&/^\d+$/.test(item)?item:undefined).filter(id=>id!=null);
  const failed=new Set(identifiedFailures.map(String));
  ids=ids.filter(id=>!failed.has(String(id)));
  if((Number(record.failed_count||record.error_count||(typeof record.failed==="number"?record.failed:0))>0||failures.length>0)&&!failed.size&&!record.successful_ids&&!record.deleted_ids&&!record.archived_ids&&!Array.isArray(record.items))ids=[];
  if(typeof record.updated_count==="number"&&record.updated_count<ids.length&&!record.successful_ids&&!failed.size)ids=[];
  const patch=(input.values||input.task||input.patch||input) as Record<string,unknown>;
  const kind=resource.match(/^\/catalog\/items\/(product|service)$/)?.[1];
  return {url,method,record,resource,ids,operation,patch,kind};
}

export function removedRecordIds(change:RecordSaved,resource:string) {
  const description=change.resource?change:confirmedMutation(change.url,change.method,{},change.record);
  return description.operation==="delete"&&resourcePath(description.resource||"")===resourcePath(resource)?description.ids||[]:[];
}

export function matchesRecordQuery(queryKey:readonly unknown[],change:RecordSaved) {
  const parts=resourcePath(change.resource||change.url).split("/").filter(Boolean);
  const module=recordNamespaces.includes(parts[0])&&parts.length>1?parts[0]:undefined;
  const resource=parts[module?1:0];
  if(!resource)return false;
  const keys=queryKey.filter((key):key is string=>typeof key==="string");
  if(keys.some(key=>key.startsWith("/")&&affectsResource(key,change.resource||change.url)))return true;
  const tokens=keys.join("/").replace(/([a-z])([A-Z])/g,"$1-$2").toLowerCase().split(/[^a-z0-9]+/);
  if(module&&["crm","srm","fam","project-management"].includes(module)&&["crm","srm","fam","pms","hrms"].some(name=>tokens.includes(name)&&name!==module&&!(name==="pms"&&module==="project-management")))return false;
  const names=[resource,resource.endsWith("ies")?`${resource.slice(0,-3)}y`:resource.replace(/s$/,"")];
  return names.some(name=>{const words=name.split("-");return tokens.some((_,index)=>words.every((word,offset)=>tokens[index+offset]===word));});
}

export function reconcileRecordList(data:unknown,change:RecordSaved):unknown {
  if(!data||typeof data!=="object")return data;
  if(!Array.isArray(data)&&"data" in data){const value=data as Record<string,unknown>;const next=reconcileRecordList(value.data,change);return next===value.data?data:{...value,data:next};}
  const value=data as Record<string,any>;
  if(!Array.isArray(data)&&value.id!=null)return data;
  const key=Array.isArray(data)?null:["rows","items","results","records"].find(key=>Array.isArray(value[key]));
  if(key===undefined)return data;
  const rows=(key===null?data:value[key]) as Record<string,any>[];
  const ids=new Set((change.ids||[]).map(String));
  const record=(change.record?.task||change.record) as Record<string,unknown>;
  if(record?.id!=null)ids.add(String(record.id));
  const kind=change.kind||(resourcePath(change.url).startsWith("/catalog/items/")?record?.kind:undefined);
  if(!ids.size)return data;
  let changed=false,removed=0;
  const next=rows.flatMap(row=>{
    if(!row||typeof row!=="object"||row.id==null||!ids.has(String(row.id))||kind&&row.kind!==kind)return [row];
    if(change.operation==="delete"){changed=true;removed++;return [];}
    const patch=record?.id!=null?record:change.patch||{};
    const fields=Object.fromEntries(Object.entries(patch).filter(([key])=>key in row&&!["id","version","expected_version"].includes(key)));
    if(!Object.keys(fields).length)return [row];
    changed=true;return [{...row,...fields,...(record?.version!=null?{version:record.version}:{})}];
  });
  if(!changed)return data;
  if(key===null)return next;
  return {...value,[key]:next,...Object.fromEntries(["total","pageTotal","count"].filter(key=>typeof value[key]==="number").map(key=>[key,Math.max(0,value[key]-removed)]))};
}

export function publishQueryMutation(client:QueryClient,change:RecordSaved,keys:string[]) {
  for(const key of keys)client.setQueriesData({queryKey:[key],predicate:query=>!["srm","fam","crm","hrms","project-management"].includes(key)||matchesRecordQuery(query.queryKey,change)},data=>reconcileRecordList(data,change));
}

export function resourcePath(url: string) {
  return url.split("?")[0].replace(/^\/api\/v1/, "").replace(/^\/hrms\//, "/").replace(/^\/pms\//, "/project-management/")
    .replace(/^\/project-management\/(?:task-studio\/)?projects\/\d+\/tasks/, "/project-management/tasks")
    .replace(/^\/project-management\/task-studio\/tasks/, "/project-management/tasks").replace(/\/$/, "");
}
export function affectsResource(read: string, mutation: string) {
  const a = resourcePath(read), b = resourcePath(mutation);
  return a === b || b.startsWith(`${a}/`);
}

/** Refresh matching query observers in place; retain their data and UI state. */
export function installRecordListRefresh(client: QueryClient) {
  const changed = (event: Event) => {
    const detail=(event as CustomEvent<RecordSaved>).detail;
    const change=detail.resource?detail:confirmedMutation(detail.url,detail.method,{},detail.record);
    const parts = resourcePath(change.resource||change.url).split("/").filter(Boolean);
    const module = recordNamespaces.includes(parts[0]) && parts.length>1 ? parts[0] : undefined;
    const resource = parts[module ? 1 : 0];
    if (!resource) return;
    const matches=(query:{queryKey:readonly unknown[]})=>matchesRecordQuery(query.queryKey,change);
    for(const query of client.getQueryCache().getAll()) {
      if(!matches(query))continue;
      const first=String(query.queryKey[0]||"");
      const primary=first==="shared-grid"||["universal-contacts","master-companies","catalog-items"].includes(first)||first===resource||first===`${module}-${resource}`||first===module&&String(query.queryKey[1]).replace(/([a-z])([A-Z])/g,"$1-$2").toLowerCase()===resource;
      if(primary&&!parts.some(part=>/^\d+$/.test(part)))client.setQueryData(query.queryKey,(data:unknown)=>reconcileRecordList(data,change));
    }
    void client.invalidateQueries({ predicate: matches });
  };
  window.addEventListener(recordSavedEvent, changed);
  return () => window.removeEventListener(recordSavedEvent, changed);
}
