/** Read-only local intents. Mutations always continue to the governed operator. */
export type RadarRequest = { id:number; horizon?:number; filter?:'all'|'overdue' };
export function parseRadarRequest(text:string):Omit<RadarRequest,'id'>|null {
 const match=text.trim().match(/^(?:please )?(?:create|build|show|open)(?: me)?(?: an?| the| my)? (deadline radar|upcoming deadlines|overdue deadlines)(?: (?:for )?(?:the )?next (\d{1,3}) days)?[.!?]?$/i);
 if(!match)return null;
 const horizon=match[2]?Number(match[2]):undefined;
 if(horizon!==undefined&&(horizon<1||horizon>365))return null;
 return {horizon,filter:match[1].toLowerCase()==='overdue deadlines'?'overdue':'all'};
}
