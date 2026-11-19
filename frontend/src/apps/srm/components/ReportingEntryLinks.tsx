import {Link} from 'react-router-dom';
import {useQuery} from '@tanstack/react-query';
import {api} from '@/services/api';
import {useRecordScope} from '@/lib/record-scope';
import {reportHref} from '../report-navigation';
import type {ReportMeta} from '../reporting-types';

/** Probe the existing native report gate; selected packs keep their own reports. */
export default function ReportingEntryLinks(){
 const scope=useRecordScope();
 const access=useQuery({queryKey:['srm','reporting','metadata',scope],queryFn:async({signal})=>(await api.get<ReportMeta>('/srm/reporting/metadata',{signal,recordCache:false,progress:false})).data,staleTime:30000,retry:false});
 if(!access.isSuccess)return null;
 const links=[
  {key:'overview',label:'Daily business dashboard',to:reportHref('overview')},
  {key:'reconciliation',label:'Opening / closing stock reconciliation',to:reportHref('reconciliation')},
  {key:'stock',label:'Low-stock planning & PO drafts',to:reportHref('stock',{low:true})},
  {key:'customers',label:'Customer insights & purchase history',to:reportHref('customers')},
  {key:'overview',label:'Saved reports',to:reportHref('overview',{panel:'saved'})},
  {key:'overview',label:'Daily / weekly summaries',to:reportHref('overview',{panel:'summary'})},
 ].filter(link=>access.data.reports.some(report=>report.key===link.key));
 return <section aria-label="Business report shortcuts" className="rounded-xl border bg-card p-4 space-y-3"><h2 className="font-semibold">Business reports</h2><p className="text-sm text-muted-foreground">Open the daily dashboard, stock movement equation, reorder planner or customer history for the current company and branch.</p><div className="flex flex-wrap gap-2">{links.map(link=><Link key={link.label} to={link.to} className="rounded-md border px-3 py-2 text-sm font-medium text-primary hover:bg-accent">{link.label}</Link>)}</div></section>;
}
