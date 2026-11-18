/** Screen pagination keeps existing React nodes, event handlers and draft state mounted. */
export type ScreenPage = { units: HTMLElement[]; label: string };
const ignored = 'script,style,link,template,thead,[hidden],[role="dialog"],[data-srm-mobile-ignore]';
const atomic = 'input,textarea,select,button,a,p,label,legend,h1,h2,h3,h4,h5,h6,svg,canvas,iframe,.udg-scroll,.scheduler-scroll,[contenteditable="true"],[data-srm-mobile-keep]';
const labelOf = (element:HTMLElement) => (element.querySelector('h2,h3,h4,legend,caption')?.textContent || element.getAttribute('aria-label') || element.innerText?.split('\n').find(text=>text.trim()) || 'Details').trim().slice(0,65);

export function clearScreenPagination(root:HTMLElement) {
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
  root.querySelectorAll<HTMLElement>('div,section,article,ul,ol').forEach(element=>{
    if(!element.getClientRects().length)return;
    const style=getComputedStyle(element);
    const horizontal=/auto|scroll/.test(style.overflowX)&&element.scrollWidth>element.clientWidth+2;
    const vertical=/auto|scroll/.test(style.overflowY)&&element.scrollHeight>element.clientHeight+2;
    const native=element.matches('.udg-scroll,.scheduler-scroll,[role="grid"]')||/gantt|scheduler|calendar|virtual|editor|chat|message|conversation|thread/.test(element.className);
    if(element.matches('.udg-scroll,.scheduler-scroll,[role="grid"]')||horizontal||native&&vertical)element.dataset.srmNativeScroller='true';
    else if(vertical)element.dataset.srmFlowContainer='true';
  });
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
    unit.dataset.srmPageUnit='true';
    const style=getComputedStyle(unit);
    const height=unit.getBoundingClientRect().height+(parseFloat(style.marginTop)||0)+(parseFloat(style.marginBottom)||0)+12;
    if(!pages.length||used+height>budget){pages.push({units:[],label:labelOf(unit)});used=0;}
    pages[pages.length-1].units.push(unit);used+=height;
  }
  if(!pages.length)return [{units:[],label:'Overview'}];
  // Account for real card padding and layout gaps, rather than assuming uniform rows.
  for(let index=0;index<pages.length;index++){
    const page=pages[index];applyScreenPage(root,viewport,pages,index);
    let overflow=viewport.scrollHeight-viewport.clientHeight;
    while(overflow>2&&page.units.length>1){
      const last=page.units.pop()!;
      if(!pages[index+1])pages.push({units:[],label:labelOf(last)});
      pages[index+1].units.unshift(last);pages[index+1].label=labelOf(pages[index+1].units[0]);
      applyScreenPage(root,viewport,pages,index);overflow=viewport.scrollHeight-viewport.clientHeight;
    }
    if(overflow>2&&page.units.length===1){
      const unit=page.units[0];unit.dataset.srmPageOversize='true';
      unit.style.setProperty('--srm-unit-height',`${Math.max(56,unit.getBoundingClientRect().height-overflow-8)}px`);
    }
  }
  return pages;
}

export function applyScreenPage(root:HTMLElement,viewport:HTMLElement,pages:ScreenPage[],index:number){
  const all=pages.flatMap(page=>page.units),active=pages[index]?.units||[];
  const parents=new Set<HTMLElement>();
  all.forEach(unit=>{
    unit.dataset.srmPageHidden=String(!active.includes(unit));
    for(let parent=unit.parentElement;parent&&parent!==root;parent=parent.parentElement)parents.add(parent);
  });
  parents.forEach(parent=>{parent.dataset.srmPageHidden=String(!active.some(unit=>parent.contains(unit)));});
  viewport.scrollTop=0;viewport.scrollLeft=0;
}
