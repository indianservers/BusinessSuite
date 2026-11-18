import type {AuthUser} from '@/store/authStore';
import {canAccessRoute} from './roles';
import {moduleActionAllowed} from '@/hooks/use-module-action';
import {contextualDestination} from '@/shared/creation/registry';
import {workspacePageHref} from './navigation-workspaces';

const targetURL=(to:string)=>new URL(to,'https://suite.local');
export function mobileDockCreatesRecord(label:string,to:string){
 const target=targetURL(to);
 return /^(?:Add|Create|Apply)\b/i.test(label)||/\/(?:new|create)\/?$/.test(target.pathname)||target.searchParams.has('new')||target.hash==='#new-record';
}

/** Match existing creation affordances without changing server authorization. */
export function mobileDockActionAllowed(user:AuthUser|null|undefined,label:string,to:string){
 const path=targetURL(to).pathname;
 if(!user||!canAccessRoute(path,user.role,user.is_superuser))return false;
 const hrmsRole=user.access?.grants.hrms?.role||user.role||'';
 const personalHR=!user.is_superuser&&(user.role==='employee'||/employee|intern|self|member/i.test(hrmsRole));
 if(personalHR&&['/hrms/payroll','/hrms/statutory-compliance','/hrms/fnf-settlements'].includes(path))return false;
 if(path==='/hrms/leave'&&label==='Apply for leave'&&!user.employee_id)return false;
 if(!mobileDockCreatesRecord(label,to))return true;
 return !user.access?.managed||moduleActionAllowed(user,path,'create');
}

/** Carry selected workspace/project and creation associations, not list filters. */
export function mobileDockHref(to:string,origin:{pathname:string;search:string},label=''){
 const source=new URLSearchParams(origin.search);
 const project=origin.pathname.match(/^\/pms\/projects\/(\d+)(?:\/|$)/)?.[1];
 if(project&&!source.has('project')&&!source.has('projectId'))source.set('project',project);
 if(!source.has('workspace')&&source.has('workspace_id'))source.set('workspace',source.get('workspace_id')!);
 const create=mobileDockCreatesRecord(label,to);
 const target=targetURL(create?contextualDestination(to,origin):to);
 const withWorkspace=targetURL(workspacePageHref(target.pathname+target.search,source.toString()));
 target.search=withWorkspace.search;
 if(create){
  for(const key of ['customer_id','company_id','contact_id','lead_id','deal_id','sales_order_id','contract_id','engagement_id']){
   const value=source.get(key);if(value&&/^\d+$/.test(value)&&!target.searchParams.has(key))target.searchParams.set(key,value);
  }
  const record=origin.pathname.match(/^\/(crm|srm)\/(customers|companies|accounts|contacts|leads|deals|sales-orders|contracts|engagements)\/(\d+)(?:\/|$)/);
  if(record){const key=record[2]==='customers'&&record[1]==='crm'?'company_id':({customers:'customer_id',companies:'company_id',accounts:'company_id',contacts:'contact_id',leads:'lead_id',deals:'deal_id','sales-orders':'sales_order_id',contracts:'contract_id',engagements:'engagement_id'} as Record<string,string>)[record[2]];if(!target.searchParams.has(key))target.searchParams.set(key,record[3]);}
 }
 return target.pathname+target.search+target.hash;
}
