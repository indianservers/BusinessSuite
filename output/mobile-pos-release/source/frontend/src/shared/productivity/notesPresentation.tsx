export function Highlight({text,query}:{text:string;query:string}){
  const term=query.trim();if(!term)return <>{text}</>;
  const pieces:React.ReactNode[]=[];let start=0;const lower=text.toLowerCase(),needle=term.toLowerCase();let index=lower.indexOf(needle);
  while(index!==-1){pieces.push(text.slice(start,index),<mark key={index}>{text.slice(index,index+term.length)}</mark>);start=index+term.length;index=lower.indexOf(needle,start);}pieces.push(text.slice(start));return <>{pieces}</>;
}
export function editedLabel(value:string){const seconds=Math.max(0,(Date.now()-new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)?value:value+"Z").getTime())/1000);if(seconds<60)return "Just now";if(seconds<3600)return `${Math.floor(seconds/60)}m ago`;if(seconds<86400)return `${Math.floor(seconds/3600)}h ago`;if(seconds<604800)return `${Math.floor(seconds/86400)}d ago`;return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)?value:value+"Z").toLocaleDateString(undefined,{month:"short",day:"numeric"});}
