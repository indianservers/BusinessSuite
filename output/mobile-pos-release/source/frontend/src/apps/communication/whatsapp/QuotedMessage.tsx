export type ReplyTarget={id:number;body:string;direction?:string};
export type MessageQuote={id?:number;providerMessageId?:string;body:string;direction?:string};
export default function QuotedMessage({quote,jump}:{quote:MessageQuote;jump?:(id:number)=>void}){
  return <button type="button" className="wa-quoted-message" disabled={!quote.id||!jump} onClick={()=>quote.id&&jump?.(quote.id)}><strong>{quote.direction==='outbound'?'You':quote.direction==='inbound'?'Customer':'Quoted message'}</strong><span>{quote.body||'Original message unavailable'}</span></button>;
}
