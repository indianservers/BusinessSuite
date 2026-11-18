export type BotModule='CRM'|'PMS'|'HRMS'|'SRM'|'FAM';
export function actionBotContext(path:string,search:string){
 const params=new URLSearchParams(search);
 const positive=(value:string|null|undefined)=>value&&/^[1-9]\d*$/.test(value)&&Number.isSafeInteger(Number(value))?Number(value):undefined;
 const module:BotModule|undefined=/^\/crm(?:\/|$)/.test(path)?'CRM':/^\/pms(?:\/|$)/.test(path)?'PMS':/^\/srm(?:\/|$)/.test(path)?'SRM':/^\/fam(?:\/|$)/.test(path)?'FAM':/^\/(?:hrms|employees|employee-directory|leave|attendance|payroll|helpdesk|daily-work|my-assignments)(?:\/|$)/.test(path)?'HRMS':undefined;
 return {module,workspace_id:positive(params.get('workspace')||params.get('workspace_id')),project_id:module==='PMS'?positive(path.match(/\/projects\/([1-9]\d*)\b/)?.[1]||params.get('project')||params.get('project_id')):undefined};
}
