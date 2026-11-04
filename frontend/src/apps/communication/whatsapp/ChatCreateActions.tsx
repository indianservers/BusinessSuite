import { lazy, Suspense, useState } from 'react';
import { Dialog,DialogContent,DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import { useCenterScope } from '../center/shared';
const Deal=lazy(()=>import('@/apps/crm/CRMWorkspacePage').then(m=>({default:m.QuickDealDialog})));
const Quote=lazy(()=>import('@/apps/crm/CRMRecordDetailPage').then(m=>({default:m.QuickActionModal})));
const Invoice=lazy(()=>import('@/apps/srm/pages/SRMWorkspacePage').then(m=>({default:m.ManualInvoiceComposer})));
const Task=lazy(()=>import('@/apps/project-management/pages/TaskStudioPage'));
export type Creation={personId:number|null;companyId:number|null;dealId:number|null;canDeal:boolean;canQuotation:boolean;canInvoice:boolean;canTask:boolean};
type Source={id:number;name:string;entity:'leads'|'contacts'|'companies'|'deals'};
export default function ChatCreateActions({contactId,source,creation,saved}:{contactId:number;source:Source;creation:Creation;saved:()=>Promise<void>}){
  const [busy,setBusy]=useState(false);
  const scope=useCenterScope(),[action,setAction]=useState<'deal'|'quotation'|'invoice'|'task'|null>(null);
  const draftScope=`whatsapp:${scope}:${contactId}`;
  async function done(){setBusy(false);setAction(null);await saved();}
  const related={contact_id:creation.personId||undefined,company_id:creation.companyId||undefined,deal_id:creation.dealId||undefined};
  return <section className="wa-chat-create"><h4>Create from this conversation</h4><div>{([['deal','Create deal',creation.canDeal],['quotation','Create quotation',creation.canQuotation],['invoice','Create invoice',creation.canInvoice],['task','Create PMS task',creation.canTask]] as const).map(([key,label,allowed])=><Button key={key} size="sm" variant="outline" disabled={!allowed} onClick={()=>setAction(key)}>{label}</Button>)}</div>{!creation.personId&&<small>Link a person to create linked sales records. PMS tasks can also link to leads.</small>}{!creation.companyId&&<small>A linked customer company is required for invoice creation.</small>}
    <Suspense fallback={<p role="status">Loading shared creation form…</p>}>
      {action==='deal'&&<Deal draftScope={draftScope} initialValues={{contactId:creation.personId||'',companyId:creation.companyId||'',name:`Opportunity · ${source.name}`,source:'WhatsApp'}} close={()=>setAction(null)} saved={()=>void done()}/>}
      {action==='quotation'&&<Quote action="quotation" kind={source.entity==='companies'?'accounts':source.entity} record={{id:source.id,...related}} entity={source.entity} recordId={source.id} initialValues={related} onClose={()=>setAction(null)} onDone={()=>void done()}/>}
      {(action==='invoice'||action==='task')&&<Dialog open onOpenChange={open=>{if(!open&&!busy)setAction(null);}}><DialogContent className="wa-create-dialog" onPointerDownOutside={e=>e.preventDefault()}><DialogTitle>{action==='invoice'?'Create invoice':'Create PMS task'} · {source.name}</DialogTitle>{action==='invoice'?<Invoice onBusyChange={setBusy} initialCustomerId={creation.companyId||undefined} initialContactId={creation.personId||undefined} onCreated={()=>void done()}/>:<Task onBusyChange={setBusy} embedded draftScope={draftScope} initialTitle={`Follow up · ${source.name}`} initialDescription={`From WhatsApp conversation #${contactId}. CRM ${source.entity} #${source.id}.`} onClose={()=>{if(!busy)setAction(null);}} onCreated={async task=>{
        const kind=source.entity==='leads'?'lead':'contact',id=kind==='lead'?source.id:creation.personId;
        if(!id)throw new Error('Link a person or lead before creating a CRM-linked task.');
        await api.post(`/project-management/task-workspace/tasks/${task.id}/crm-links`,{kind,record_id:id});
        await done();
      }}/>}</DialogContent></Dialog>}
    </Suspense>
  </section>;
}
