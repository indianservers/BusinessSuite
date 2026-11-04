import { useState } from "react";

/** Cursor history is local to one record/filter/access scope, never shared across scopes. */
export function useCursorPages(key:string){
  type State={key:string;cursors:(string|null)[];index:number};
  const [stored,setStored]=useState<State>({key,cursors:[null],index:0});
  const state=stored.key===key?stored:{key,cursors:[null],index:0};
  return {page:state.index+1,cursor:state.cursors[state.index],
    next:(cursor:string|null)=>setStored({key,cursors:[...state.cursors.slice(0,state.index+1),cursor],index:state.index+1}),
    previous:()=>setStored({key,cursors:state.index===1?[null]:state.cursors,index:Math.max(0,state.index-1)}),
    reset:()=>setStored({key,cursors:[null],index:0})};
}
