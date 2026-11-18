import PrivateSavedViews from '@/shared/records/PrivateSavedViews';
export type TaskView={queue:string;status:string;priority:string;mine:boolean;sort:string;search:string};
type LegacyView={name:string;filters:TaskView};
function valid(value:any):value is LegacyView{return !!value&&typeof value.name==='string'&&value.name.trim().length>0&&value.name.length<=60&&
 !!value.filters&&typeof value.filters.mine==='boolean'&&typeof value.filters.search==='string'&&value.filters.search.length<=300&&
 typeof value.filters.status==='string'&&value.filters.status.length<=80&&typeof value.filters.priority==='string'&&value.filters.priority.length<=60&&
 ['all','open','completed','overdue','today','week','unscheduled'].includes(value.filters.queue)&&['due_date:asc','due_date:desc','created_at:desc','title:asc'].includes(value.filters.sort)}

export default function TaskSavedViews(props:{scope:string;filters:TaskView;onApply:(view:TaskView)=>void}){
 return <PrivateSavedViews {...props} endpoint="/crm/task-views" title="Private CRM task views" legacyPrefix="crm.task-views.v1" validLegacy={valid}/>;
}
