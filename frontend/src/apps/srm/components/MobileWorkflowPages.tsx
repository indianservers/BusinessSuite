import { useCallback, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { useMobile } from '@/components/mobile/useMobile';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { applyScreenPage, clearScreenPagination, measureScreenPages, type ScreenPage } from './mobile-screen-pages';
import './mobile-workflow-pages.css';

/** Page the original controls without remounting fields or replacing native submits. */
export default function MobileWorkflowPages({children,resetKey}:{children:ReactNode;resetKey?:string|number}) {
  const mobile=useMobile();
  return mobile?<WorkflowPages resetKey={resetKey}>{children}</WorkflowPages>:<>{children}</>;
}
function WorkflowPages({children,resetKey}:{children:ReactNode;resetKey?:string|number}) {
  const root=useRef<HTMLDivElement>(null),view=useRef<HTMLDivElement>(null),pages=useRef<ScreenPage[]>([]),selected=useRef(0),frame=useRef(0),feedback=useRef<HTMLElement|null>(null);
  const [model,setModel]=useState({page:0,count:1,label:'Details'});
  const goto=useCallback((page:number)=>{if(!root.current||!view.current)return;selected.current=Math.max(0,Math.min(page,pages.current.length-1));applyScreenPage(root.current,view.current,pages.current,selected.current);setModel({page:selected.current,count:pages.current.length,label:pages.current[selected.current]?.label||'Details'});},[]);
  useLayoutEffect(()=>{
    const documentRoot=root.current,viewport=view.current;if(!documentRoot||!viewport)return;selected.current=0;
    const measure=()=>{frame.current=0;const active=document.activeElement instanceof HTMLElement&&documentRoot.contains(document.activeElement)?document.activeElement:null;const anchor=feedback.current||active;const next=measureScreenPages(documentRoot,viewport);let index=anchor?next.findIndex(page=>page.units.some(unit=>unit===anchor||unit.contains(anchor))):-1;if(index<0)index=Math.min(selected.current,next.length-1);pages.current=next;selected.current=index;applyScreenPage(documentRoot,viewport,next,index);if(feedback.current){feedback.current.tabIndex=-1;feedback.current.focus({preventScroll:true});feedback.current=null;}const model={page:index,count:next.length,label:next[index]?.label||'Details'};setModel(current=>JSON.stringify(current)===JSON.stringify(model)?current:model);};
    const schedule=()=>{if(!frame.current)frame.current=requestAnimationFrame(measure);};
    const mutations=new MutationObserver(records=>{for(const record of records)for(const node of Array.from(record.addedNodes)){if(node instanceof HTMLElement){const alert=node.matches('[role=alert]')?node:node.querySelector<HTMLElement>('[role=alert]');if(alert)feedback.current=alert;}}schedule();});mutations.observe(documentRoot,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['open','aria-expanded']});
    const resize=new ResizeObserver(schedule);resize.observe(viewport);resize.observe(documentRoot);measure();return()=>{cancelAnimationFrame(frame.current);resize.disconnect();mutations.disconnect();clearScreenPagination(documentRoot);};
  },[resetKey]);
  return <div className="mobile-workflow-pages"><div className="mobile-workflow-viewport" ref={view}><div className="mobile-workflow-document" ref={root} onInvalidCapture={event=>{const target=event.target as HTMLElement;const index=pages.current.findIndex(page=>page.units.some(unit=>unit===target||unit.contains(target)));if(index>=0){goto(index);requestAnimationFrame(()=>target.focus({preventScroll:true}));}}}>{children}</div></div>{model.count>1&&<nav className="mobile-workflow-pagination" aria-label="Workflow steps"><button type="button" aria-label="Previous step" disabled={!model.page} onClick={()=>goto(model.page-1)}><ArrowLeft size={17}/></button><span><strong>{model.label}</strong><small>Step {model.page+1} of {model.count}</small></span><button type="button" aria-label="Next step" disabled={model.page>=model.count-1} onClick={()=>goto(model.page+1)}><ArrowRight size={17}/></button></nav>}</div>;
}
export function MobileWorkflowSurface({title,children,onClose,enabled=true}:{title:string;children:ReactNode;onClose:()=>void;enabled?:boolean}) {
  const mobile=useMobile();
  return mobile&&enabled?<Dialog open onOpenChange={open=>{if(!open)onClose();}}><DialogContent className="mobile-workflow-dialog"><DialogTitle>{title}</DialogTitle><DialogDescription className="sr-only">Complete this booking workflow. Your entries are kept when changing steps.</DialogDescription><MobileWorkflowPages>{children}</MobileWorkflowPages></DialogContent></Dialog>:<>{children}</>;
}
