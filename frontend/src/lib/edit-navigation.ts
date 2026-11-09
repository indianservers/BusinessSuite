let editing = 0;
export const editNavigationActive = () => editing > 0;
export function markEditNavigation() { editing++; queueMicrotask(() => { editing = Math.max(0, editing - 1); }); }
export function withEditNavigation<T>(action: {id?:string;label?:string;kind?:string}, run:()=>T):T {
  if (![action.id,action.label,action.kind].some(value=>/^(edit|update)(\b|-)/i.test(value||""))) return run();
  editing++;try{return run();}finally{editing--;}
}
export function openEditDestination(destination:string) {
  const detail={destination,handled:false};window.dispatchEvent(new CustomEvent("suite:open-editor",{detail}));return detail.handled;
}
