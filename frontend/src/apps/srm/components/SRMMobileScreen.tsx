import ModuleNewMenu from "@/components/app/ModuleNewMenu";
import ErrorBoundary from "@/components/app/ErrorBoundary";
import { LoadingState } from "@/components/ui/state";
import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { flushSync } from 'react-dom';
import * as Dialog from '@radix-ui/react-dialog';
import { ArrowLeft, ArrowRight, ChevronDown, LayoutGrid, Menu, Search, ShoppingBag, X } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useMobile } from '@/components/mobile/useMobile';
import SuiteNotificationBell from '@/components/suite/SuiteNotificationBell';
import { canAccessRoute, getRoleNav } from '@/lib/roles';
import { useAuthStore } from '@/store/authStore';
import { applyScreenPage, clearScreenPagination, measureScreenPages, type ScreenPage } from './mobile-screen-pages';
import './srm-mobile-screen.css';

const titleFor=(path:string)=>path.replace(/\/srm\/?/,'').split('/').filter(value=>value&&!/^\d+$/.test(value)&&!value.startsWith(':')).slice(-2).join(' · ').replace(/-/g,' ').replace(/\b\w/g,value=>value.toUpperCase())||'Sales & Revenue';
export default function SRMMobileScreen({children,paths,nativePath}:{children:ReactNode;paths:string[];nativePath?:string}){
  const mobile=useMobile(),location=useLocation();
  const operation=new URLSearchParams(location.search).get('operation')||nativePath||location.pathname;
  const terminal=/^\/srm\/pos(?:\/terminal)?\/?$/.test(operation);
  return !mobile||terminal||/^\/srm\/(appointments|service-scheduling)\/?$/.test(operation)?<>{children}</>:<MobileScreen key={location.pathname} paths={paths}>{children}</MobileScreen>;
}
function MobileScreen({children,paths}:{children:ReactNode;paths:string[]}){
  const location=useLocation(),navigate=useNavigate(),user=useAuthStore(state=>state.user);
  const root=useRef<HTMLDivElement>(null),viewport=useRef<HTMLDivElement>(null),screen=useRef<HTMLDivElement>(null);
  const pages=useRef<ScreenPage[]>([]),selected=useRef(0),frame=useRef(0),manualNavigation=useRef(false),pendingActionAt=useRef(0),preferredTarget=useRef<HTMLElement|null>(null);
  const [model,setModel]=useState({page:0,labels:['Overview']});
  const [title,setTitle]=useState(titleFor(location.pathname));
  const [summary,setSummary]=useState('SALES WORKSPACE');
  const [botAvailable,setBotAvailable]=useState(false);
  const [screenHeight,setScreenHeight]=useState(()=>window.visualViewport?.height||window.innerHeight);
  useEffect(()=>setBotAvailable(!!document.querySelector('.action-bot-launcher')),[]);
  const [sheet,setSheet]=useState<'menu'|'sections'|null>(null),[search,setSearch]=useState(''),[menuPage,setMenuPage]=useState(0);
  const goto=useCallback((index:number)=>{
    if(!root.current||!viewport.current)return;
    const page=Math.max(0,Math.min(index,pages.current.length-1));selected.current=page;manualNavigation.current=true;
    applyScreenPage(root.current,viewport.current,pages.current,page);
    setModel(current=>({...current,page}));
  },[]);
  useLayoutEffect(()=>{
    const documentRoot=root.current,view=viewport.current;if(!documentRoot||!view)return;
    let disposed=false;const previousHeight=document.body.style.getPropertyValue('--srm-visual-height');
    const measure=()=>{
      frame.current=0;if(disposed)return;
      const active=document.activeElement instanceof HTMLElement&&documentRoot.contains(document.activeElement)&&document.activeElement.matches('input:not([type="checkbox"]):not([type="radio"]),textarea,[contenteditable="true"]')?document.activeElement:null;
      const feedback=preferredTarget.current;
      const anchor=feedback||(manualNavigation.current?null:active);
      const next=measureScreenPages(documentRoot,view);
      let page=anchor?next.findIndex(entry=>entry.units.some(unit=>unit===anchor||unit.contains(anchor))):-1;
      if(page<0)page=Math.min(selected.current,next.length-1);
      pages.current=next;selected.current=page;applyScreenPage(documentRoot,view,next,page);
      if(feedback&&next[page].units.some(unit=>unit===feedback||unit.contains(feedback))){feedback.tabIndex=-1;feedback.focus({preventScroll:true});preferredTarget.current=null;pendingActionAt.current=0;}
      const count=documentRoot.querySelector('.udg-summary-footer strong,.bookings-agenda-strip strong,.mobile-schedule-toolbar strong')?.textContent?.trim();setSummary(count||'SALES WORKSPACE');
      const heading=Array.from(documentRoot.querySelectorAll('h1')).find(heading=>!heading.closest('[hidden],[aria-hidden="true"]'))?.textContent?.trim();if(documentRoot.querySelector('[data-srm-native-pages]'))setTitle("Calendar");else if(heading)setTitle(heading);
      const labels=next.map(entry=>entry.label);
      setModel(current=>current.page===page&&JSON.stringify(current.labels)===JSON.stringify(labels)?current:{page,labels});
    };
    const schedule=()=>{if(!frame.current)frame.current=requestAnimationFrame(measure);};
    const mutations=new MutationObserver(records=>{
      if(pendingActionAt.current&&Date.now()-pendingActionAt.current<15000){
        for(const record of records){
          const nodes=record.type==='characterData'?[record.target.parentElement]:Array.from(record.addedNodes);
          for(const node of nodes){if(!(node instanceof HTMLElement))continue;const alert=node.closest<HTMLElement>('[role="alert"]')||node.querySelector<HTMLElement>('[role="alert"]');if(alert&&!alert.closest('[hidden],[aria-hidden="true"]'))preferredTarget.current=alert;}
        }
      }
      schedule();
    });mutations.observe(documentRoot,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['open','hidden','aria-expanded','aria-selected']});
    const resize=new ResizeObserver(schedule);resize.observe(view);resize.observe(documentRoot);
    const height=()=>{const pixels=window.visualViewport?.height||window.innerHeight;setScreenHeight(pixels);const value=`${pixels}px`;screen.current?.style.setProperty('--srm-screen-height',value);document.body.style.setProperty('--srm-visual-height',value);schedule();};
    window.addEventListener('resize',height);window.visualViewport?.addEventListener('resize',height);height();measure();
    return()=>{disposed=true;if(previousHeight)document.body.style.setProperty('--srm-visual-height',previousHeight);else document.body.style.removeProperty('--srm-visual-height');cancelAnimationFrame(frame.current);mutations.disconnect();resize.disconnect();window.removeEventListener('resize',height);window.visualViewport?.removeEventListener('resize',height);clearScreenPagination(documentRoot);};
  },[]);
  useEffect(()=>{goto(0);},[location.search,goto]);
  const nativeInvalid=(event:React.InvalidEvent<HTMLDivElement>)=>{
    const target=event.target as HTMLElement;
    const index=pages.current.findIndex(page=>page.units.some(unit=>unit===target||unit.contains(target)));
    if(index>=0){flushSync(()=>goto(index));requestAnimationFrame(()=>target.focus());}
  };
  const nav=useMemo(()=>{
    const known=getRoleNav(user?.role,user?.is_superuser,'/srm');
    const destinations=[...paths,...(/^\/srm\/(appointments|service-scheduling|scheduled-services)/.test(location.pathname)?['/srm/appointments?resources=1','/srm/service-scheduling?view=schedule&mode=Calendar']:[])];
    return [...new Set(destinations)].filter(path=>!path.includes(':')&&canAccessRoute(path,user?.role,user?.is_superuser)).map(path=>({path,label:path.includes('resources=1')?'Employees & resources':path.includes('mode=Calendar')?'Calendar':known.find(item=>item.to.split('?')[0]===path)?.label||titleFor(path)}));
  },[paths,user,location.pathname]);
  const choices=sheet==='sections'?model.labels.map((label,index)=>({key:String(index),label,detail:`Section ${index+1}`,activate:()=>goto(index)})):nav.map(entry=>({key:entry.path,label:entry.label,detail:entry.path.replace('/srm','Sales'),activate:()=>navigate(entry.path)}));
  const filtered=choices.filter(item=>`${item.label} ${item.detail}`.toLowerCase().includes(search.toLowerCase()));
  const menuSize=Math.max(1,Math.min(screenHeight<700?4:7,Math.floor((screenHeight-190)/48))),menuPages=Math.max(1,Math.ceil(filtered.length/menuSize)),safeMenuPage=Math.min(menuPage,menuPages-1);
  const openSheet=(value:'menu'|'sections')=>{setSearch('');setMenuPage(0);setSheet(value);};
  const bookingRoute=/^\/srm\/(appointments|scheduled-services|service-scheduling)/.test(location.pathname);
  return <div ref={screen} className="srm-mobile-screen" data-booking-route={bookingRoute} data-pages={model.labels.length}>
    <header className="srm-mobile-header"><button type="button" aria-label="Back to Sales" onClick={()=>navigate('/srm')}><ArrowLeft size={21}/></button><span className="srm-mobile-brand"><ShoppingBag size={23}/></span><div><small>{summary}</small><h1 title={title}>{title}</h1></div>{botAvailable&&<span className="srm-mobile-bot-slot"/>}<SuiteNotificationBell/><button type="button" aria-label="Open SRM navigation" onClick={()=>openSheet('menu')}><Menu size={22}/></button></header>
    <nav className="srm-mobile-shortcuts" aria-label="Sales shortcuts">{canAccessRoute('/srm/pos/terminal',user?.role,user?.is_superuser)&&<Link className="srm-mobile-pos-shortcut" to="/srm/pos/terminal"><ShoppingBag size={16}/>POS</Link>}<ModuleNewMenu/><button type="button" onClick={()=>openSheet('menu')}><LayoutGrid size={16}/>All pages</button></nav>
    {bookingRoute&&<div className="srm-mobile-booking-toolbar"/>}
    <div ref={viewport} className="srm-mobile-viewport" role="region" aria-label={`${title} content`}>
      <div ref={root} className="srm-mobile-document" onPointerDownCapture={()=>{manualNavigation.current=false;}} onKeyDownCapture={()=>{manualNavigation.current=false;}} onSubmitCapture={()=>{pendingActionAt.current=Date.now();}} onClickCapture={event=>{const button=(event.target as HTMLElement).closest('button');if(button&&/^(save|create|submit|apply|confirm|send|post|collect|approve|complete)\b/i.test(button.textContent?.trim()||''))pendingActionAt.current=Date.now();}} onInvalidCapture={nativeInvalid}><ErrorBoundary resetKey={location.pathname+location.search}><Suspense fallback={<LoadingState label="Loading Sales page"/>}>{children}</Suspense></ErrorBoundary></div>
    </div>
    {model.labels.length>1&&<nav className="srm-mobile-pagination" aria-label="Page sections"><button type="button" aria-label="Previous section" disabled={model.page===0} onClick={()=>goto(model.page-1)}><ArrowLeft size={17}/></button><button type="button" className="srm-mobile-current-section" onClick={()=>openSheet('sections')}><span>{model.labels[model.page]}</span><small>{model.page+1} / {model.labels.length}<ChevronDown size={13}/></small></button><button type="button" aria-label="Next section" disabled={model.page>=model.labels.length-1} onClick={()=>goto(model.page+1)}><ArrowRight size={17}/></button></nav>}
    <Dialog.Root open={sheet!==null} onOpenChange={open=>{if(!open)setSheet(null);}}><Dialog.Portal><Dialog.Overlay className="srm-mobile-sheet-overlay"/><Dialog.Content className="srm-mobile-sheet" aria-describedby={undefined}>
      <div className="srm-mobile-sheet-heading"><Dialog.Title>{sheet==='sections'?'Page sections':'Sales navigation'}</Dialog.Title><Dialog.Close aria-label="Close Sales navigation"><X size={20}/></Dialog.Close></div>
      <label className="srm-mobile-menu-search"><Search size={17}/><input aria-label="Search Sales pages" value={search} onChange={event=>{setSearch(event.target.value);setMenuPage(0);}} placeholder="Search pages or sections"/></label>
      <div className="srm-mobile-menu-items">{filtered.slice(safeMenuPage*menuSize,(safeMenuPage+1)*menuSize).map(item=><button type="button" key={item.key} onClick={()=>{item.activate();setSheet(null);}}><span>{item.label}<small>{item.detail}</small></span><ArrowRight size={16}/></button>)}{!filtered.length&&<p>No matching pages.</p>}</div>
      {menuPages>1&&<nav className="srm-mobile-menu-pages" aria-label="Navigation pages"><button type="button" aria-label="Previous navigation page" disabled={!safeMenuPage} onClick={()=>setMenuPage(safeMenuPage-1)}><ArrowLeft size={17}/></button><span>{safeMenuPage+1} / {menuPages}</span><button type="button" aria-label="Next navigation page" disabled={safeMenuPage>=menuPages-1} onClick={()=>setMenuPage(safeMenuPage+1)}><ArrowRight size={17}/></button></nav>}
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}
