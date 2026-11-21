import { createPortal } from "react-dom";
export type ReceiptSale = {invoiceNo:string;customer:string;amount:number;paid?:string;balance?:string;createdAt:string;mode:string;checkoutId?:number;localCash?:boolean;receiptNumbers?:string[];lines?:{name:string;qty:number;rate:number;appointment?:string}[]};
const money = (amount:number)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(amount);
const receiptTitle = (sale: ReceiptSale) => sale.localCash ? `Local cash acknowledgement ${sale.invoiceNo}` : `Invoice ${sale.invoiceNo}`;

export function receiptText(sale:ReceiptSale) {
  return [receiptTitle(sale), ...(sale.localCash ? ["Official invoice is issued separately."] : []), new Date(sale.createdAt).toLocaleString(),`Customer: ${sale.customer}`,
    ...(sale.lines || []).map(line=>`${line.name} x ${line.qty} @ ${money(line.rate)}${line.appointment ? `\n  Appointment: ${line.appointment}` : ''}`),
    `Total: ${money(sale.amount)}`,`Paid: ${money(Number(sale.paid || 0))}`,`Balance: ${money(Number(sale.balance || 0))}`,
    ...(sale.receiptNumbers || []).map(number=>`Receipt: ${number}`)].join('\n');
}
export function downloadReceipt(sale:ReceiptSale) {
  const url = URL.createObjectURL(new Blob([receiptText(sale)],{type:'text/plain;charset=utf-8'}));
  const link = document.createElement('a'); link.href=url;link.download=`${sale.invoiceNo.replace(/[^a-zA-Z0-9_-]/g,'-')}-receipt.txt`;link.style.display='none';document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export default function POSReceipt({sale}: {sale:ReceiptSale|null}) {
  if (!sale?.checkoutId && !sale?.localCash) return null;
  return createPortal(<article className="pos-print-receipt" aria-label={sale.localCash ? "Local cash acknowledgement" : "Confirmed receipt"}><h1>{receiptTitle(sale)}</h1>{sale.localCash && <p>Official invoice is issued separately.</p>}<p>{new Date(sale.createdAt).toLocaleString()}</p><p>Customer: {sale.customer}</p>
    {(sale.lines || []).map((line,index)=><div key={index}><strong>{line.name}</strong><p>{line.qty} x {money(line.rate)}</p>{line.appointment && <p>Appointment: {line.appointment}</p>}</div>)}
    <hr/><p>Total: {money(sale.amount)}</p><p>Paid: {money(Number(sale.paid || 0))}</p><p>Balance: {money(Number(sale.balance || 0))}</p><p>{sale.receiptNumbers?.join(', ')}</p></article>,document.body);
}
