export const reportGroups:ReadonlyArray<{name:string;keys:readonly string[]}>= [
 {name:'Business',keys:['overview','invoices','sales','payments','returns','outstanding','invoice_aging']},
 {name:'Insights',keys:['customers','products','profitability','project_profitability','customer_profitability','cash_margin','sales_to_delivery_margin','pipeline']},
 {name:'Inventory',keys:['stock','reconciliation','payment_reconciliation']},
 {name:'Commitments',keys:['contracts','recurring']},
];
const reports=new Set(reportGroups.flatMap(group=>[...group.keys]));
export function reportEntry(search:URLSearchParams){
 const requested=search.get('report')||'overview',report=reports.has(requested)?requested:'overview';
 return {report,lowOnly:['stock','reconciliation'].includes(report)&&search.get('low')==='1',saved:search.get('saved')==='1',summary:search.get('summary')==='latest'};
}
export function reportHref(report:string,options:{low?:boolean;panel?:'saved'|'summary'}={}){
 const params=new URLSearchParams({report:reports.has(report)?report:'overview'});
 if(options.low&&['stock','reconciliation'].includes(params.get('report')!))params.set('low','1');
 if(options.panel==='saved')params.set('saved','1');
 if(options.panel==='summary')params.set('summary','latest');
 return '/srm/reports?'+params.toString();
}
