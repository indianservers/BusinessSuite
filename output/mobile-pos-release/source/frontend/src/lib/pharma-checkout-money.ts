/** Preview the native tax-exclusive POS normalizer; grants no posting authority. */
export type PharmaQuoteLine = {quantity:string;price:string;discount:string;taxRate:string};

function scaled(value:string, places:number):bigint|null {
  const match=/^(\d+)(?:\.(\d+))?$/.exec(value);
  if(!match)return null;
  const fraction=match[2]||'';
  if(fraction.slice(places).replace(/0/g,''))return null;
  return BigInt(match[1])*10n**BigInt(places)+BigInt((fraction.slice(0,places).padEnd(places,'0'))||'0');
}
const halfUp=(value:bigint,divisor:bigint)=>(value*2n+divisor)/(divisor*2n);
const min=(...values:bigint[])=>values.reduce((left,right)=>left<right?left:right);
const moneyLimit=99999999999n*100n;

export function pharmaCheckoutQuote(lines:PharmaQuoteLine[], extraDiscount:string) {
  if(!lines.length||lines.length>100)return null;
  const additional=scaled(extraDiscount,2);
  if(additional===null||additional>moneyLimit)return null;
  const rows=[];
  for(const line of lines){
    const quantity=scaled(line.quantity,3),price=scaled(line.price,2),discount=scaled(line.discount,2),taxRate=scaled(line.taxRate,2);
    if(quantity===null||quantity<=0n||quantity>1000000000n*1000n||price===null||price>moneyLimit||discount===null||discount>moneyLimit||taxRate===null||taxRate>10000n)return null;
    // Match the native pre-round discount ceiling too; do not silently clamp it.
    if(discount*1000n>quantity*price)return null;
    rows.push({quantity,rawBase:quantity*price,base:halfUp(quantity*price,1000n),discount,taxRate});
  }
  const subtotal=rows.reduce((sum,row)=>sum+row.base,0n);
  const lineDiscount=rows.reduce((sum,row)=>sum+row.discount,0n);
  const taxableBeforeBill=subtotal-lineDiscount;
  if(taxableBeforeBill<additional)return null;
  const eligible=rows.map((row,index)=>row.base>row.discount?index:-1).filter(index=>index>=0);
  let remaining=additional,tax=0n;
  for(const [index,row] of rows.entries()){
    let share=0n;
    if(eligible.includes(index)){
      share=index===eligible[eligible.length-1]?remaining:min(remaining,row.base-row.discount,halfUp(additional*(row.base-row.discount),taxableBeforeBill));
      remaining-=share;
    }
    const discount=row.discount+share;
    if(discount*1000n>row.rawBase||discount>row.base)return null;
    tax+=halfUp((row.base-discount)*row.taxRate,10000n);
  }
  if(remaining)return null;
  const taxable=taxableBeforeBill-additional,grandTotal=taxable+tax;
  if(subtotal>moneyLimit||grandTotal>moneyLimit)return null;
  return {subtotal:Number(subtotal)/100,lineDiscount:Number(lineDiscount)/100,taxable:Number(taxable)/100,
    tax:Number(tax)/100,grandTotal:Number(grandTotal)/100,
    quantity:Number(rows.reduce((sum,row)=>sum+row.quantity,0n))/1000};
}
