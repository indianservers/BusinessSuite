import type { GridQuery } from "./types";

export type PersonalFilterKind = "favorites" | "frequent" | null;
export type GridPersonalFilter = {kind:PersonalFilterKind;ids?:string[];apply:(kind:PersonalFilterKind)=>void};

/** Reuse the grid's identifier restriction in every presentation of a collection. */
export function personalQuery(query:GridQuery, filter:Pick<GridPersonalFilter,"kind"|"ids">|undefined, identity:"id"|"key"="id"):GridQuery {
  if(filter?.ids===undefined)return query;
  return {...query,recordIds:filter.ids,recordIdentity:identity,recordOrder:filter.kind==="frequent",sorting:filter.kind==="frequent"?[]:query.sorting};
}
export function personalRows<T>(rows:T[],filter:Pick<GridPersonalFilter,"kind"|"ids">|undefined,getId:(row:T)=>string):T[]{
  if(filter?.ids===undefined)return rows;
  const ranks=new Map(filter.ids.map((id,index)=>[id,index]));
  const selected=rows.filter(row=>ranks.has(getId(row)));
  if(filter.kind==="frequent")selected.sort((a,b)=>ranks.get(getId(a))!-ranks.get(getId(b))!);
  return selected;
}
