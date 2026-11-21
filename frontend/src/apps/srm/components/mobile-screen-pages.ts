/** Screen pagination keeps existing React nodes, event handlers and draft state mounted. */
export type ScreenPage = { units: HTMLElement[]; label: string };
const ignored = 'script,style,link,template,thead,[hidden],[role="dialog"],[data-srm-mobile-ignore]';
const atomic = 'input,textarea,select,button,a,p,label,legend,h1,h2,h3,h4,h5,h6,svg,canvas,iframe,.udg-scroll,.scheduler-scroll,[contenteditable="true"],[data-srm-mobile-keep]';
const labelOf = (element:HTMLElement) => (element.querySelector('h2,h3,h4,legend,caption')?.textContent || element.getAttribute('aria-label') || element.innerText?.split('\n').find(text=>text.trim()) || 'Details').trim().slice(0,65);
const scrollFallbacks = new WeakMap<HTMLElement, { viewport: HTMLElement; value: string; priority: string }>();

function restoreViewportOverflow(root:HTMLElement) {
  const fallback=scrollFallbacks.get(root);
  if(!fallback)return;
  fallback.viewport.style.setProperty('overflow-y',fallback.value,fallback.priority);
  scrollFallbacks.delete(root);
}

export function clearScreenPagination(root:HTMLElement) {
  restoreViewportOverflow(root);
  root.querySelectorAll<HTMLElement>('[data-srm-page-hidden],[data-srm-page-unit],[data-srm-page-oversize],[data-srm-flow-container],[data-srm-native-scroller]').forEach(element=>{
    element.removeAttribute('data-srm-page-hidden');element.removeAttribute('data-srm-page-unit');element.removeAttribute('data-srm-page-oversize');element.removeAttribute('data-srm-flow-container');element.removeAttribute('data-srm-native-scroller');element.style.removeProperty('--srm-unit-height');
  });
}

export function measureScreenPages(root:HTMLElement, viewport:HTMLElement):ScreenPage[] {
  clearScreenPagination(root);
  const nativePages=root.querySelector<HTMLElement>('[data-srm-native-pages="true"]');
  if(nativePages)return [{units:[nativePages],label:"Bookings"}];
  const available=Math.max(100,viewport.clientHeight-6),budget=Math.max(80,available-38);
  // Native matrices become labelled record cards; their cells retain their original controls.
  root.querySelectorAll('table').forEach(table=>{
    table.dataset.srmInteractiveHead=String(!!table.tHead?.querySelector('button,input,select,[role=combobox]'));
    const headers=Array.from(table.tHead?.rows[0]?.cells || []).map(cell=>cell.textContent?.trim()||'');
    Array.from(table.tBodies).forEach(body=>Array.from(body.rows).forEach(row=>Array.from(row.cells).forEach((cell,index)=>{cell.dataset.srmField=headers[index]||'';})));
  });
  root.querySelectorAll<HTMLElement>('.udg-pagination').forEach(footer=>{
    const controls=Array.from(footer.querySelectorAll<HTMLButtonElement>('button')).filter(button=>/^(previous|next)$/i.test((button.textContent||'').trim()));
    footer.dataset.srmSinglePage=String(controls.length>=2&&controls.every(button=>button.disabled)&&/\bof\s+1\b/.test(footer.textContent||''));
  });
  // Expand capped record lists before measuring their parents. Native virtual
  // tables, conversations, editors and time canvases retain bounded panning.
  const nativeScrollers:HTMLElement[]=[];
  const flowContainers:HTMLElement[]=[];
  for(const element of root.querySelectorAll<HTMLElement>('div,section,article,ul,ol')){
    if(!element.getClientRects().length)continue;
    const style=getComputedStyle(element);
    const horizontal=/auto|scroll/.test(style.overflowX)&&element.scrollWidth>element.clientWidth+2;
    const vertical=/auto|scroll/.test(style.overflowY)&&element.scrollHeight>element.clientHeight+2;
    const native=element.matches('.udg-scroll,.scheduler-scroll,[role="grid"]')||/gantt|scheduler|calendar|virtual|editor|chat|message|conversation|thread/.test(element.className);
    if(element.matches('.udg-scroll,.scheduler-scroll,[role="grid"]')||horizontal||native&&vertical)nativeScrollers.push(element);
    else if(vertical)flowContainers.push(element);
  }
  nativeScrollers.forEach(element=>{element.dataset.srmNativeScroller='true';});
  flowContainers.forEach(element=>{element.dataset.srmFlowContainer='true';});
  const units:HTMLElement[]=[];
  const collect=(element:HTMLElement)=>{
    if(element.matches(ignored))return;
    const style=getComputedStyle(element);
    if(style.display==='none'||style.position==='fixed')return;
    if(style.display==='contents'){Array.from(element.children).forEach(child=>collect(child as HTMLElement));return;}
    if(!element.getClientRects().length)return;
    const boundedScroller=element.dataset.srmNativeScroller==='true'||element.matches('.udg-scroll,.scheduler-scroll');
    const height=element.getBoundingClientRect().height;
    if(height<1){Array.from(element.children).forEach(child=>collect(child as HTMLElement));return;}
    if(height<=budget||boundedScroller||element.matches(atomic)||!element.children.length){units.push(element);return;}
    const before=units.length;
    Array.from(element.children).forEach(child=>collect(child as HTMLElement));
    if(units.length===before&&element.textContent?.trim())units.push(element);
  };
  Array.from(root.children).forEach(child=>collect(child as HTMLElement));
  const pages:ScreenPage[]=[];
  let used=0;
  for(const unit of units){
    const style=getComputedStyle(unit);
    const height=unit.getBoundingClientRect().height+(parseFloat(style.marginTop)||0)+(parseFloat(style.marginBottom)||0)+12;
    if(!pages.length||used+height>budget){pages.push({units:[],label:labelOf(unit)});used=0;}
    pages[pages.length-1].units.push(unit);used+=height;
  }
  units.forEach(unit=>{unit.dataset.srmPageUnit='true';});
  return pages.length?pages:[{units:[],label:'Overview'}];
}

export function applyScreenPage(root:HTMLElement,viewport:HTMLElement,pages:ScreenPage[],index:number){
  const active=pages[index]?.units||[];
  const visible=new Set<HTMLElement>();
  const ancestors=(unit:HTMLElement,seen:Set<HTMLElement>)=>{
    for(let node:HTMLElement|null=unit;node&&node!==root&&!seen.has(node);node=node.parentElement)seen.add(node);
  };
  active.forEach(unit=>ancestors(unit,visible));
  const managed=new Set<HTMLElement>();
  pages.forEach(page=>page.units.forEach(unit=>ancestors(unit,managed)));
  managed.forEach(element=>{
    const hidden=visible.has(element)?'false':'true';
    if(element.dataset.srmPageHidden!==hidden)element.dataset.srmPageHidden=hidden;
  });
  // Parent padding and gaps can make a page taller after its siblings are hidden.
  // Check only the rendered page and keep any extra content reachable.
  if(viewport.scrollHeight>viewport.clientHeight+2){
    if(!scrollFallbacks.has(root)){
      scrollFallbacks.set(root,{viewport,value:viewport.style.getPropertyValue('overflow-y'),priority:viewport.style.getPropertyPriority('overflow-y')});
      viewport.style.setProperty('overflow-y','auto');
    }
  }else{
    restoreViewportOverflow(root);
  }
  viewport.scrollTop=0;viewport.scrollLeft=0;
}
