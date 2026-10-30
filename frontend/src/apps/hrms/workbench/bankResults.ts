export type BankLine={employee_id:number;payroll_record_id:number;status:string};
export type ImportLine={payroll_record_id:number;payment_status:"Paid"|"Failed";utr_number?:string;failure_reason?:string};
/** RFC 4180 fields, including escaped quotes and quoted line breaks. */
export function csvRows(text:string):string[][]{
 const rows:string[][]=[];let row:string[]=[],cell="",quoted=false;
 for(let i=0;i<text.length;i++){
  const char=text[i];
  if(char==='"'){
   if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;
  }else if(char===","&&!quoted){row.push(cell);cell="";}
  else if((char==="\n"||char==="\r")&&!quoted){if(char==="\r"&&text[i+1]==="\n")i++;row.push(cell);if(row.some(c=>c.trim()))rows.push(row);row=[];cell="";}
  else cell+=char;
 }
 if(quoted)throw Error("Unclosed quoted field in CSV");
 row.push(cell);if(row.some(c=>c.trim()))rows.push(row);
 if(rows[0]?.[0])rows[0][0]=rows[0][0].replace(/^\uFEFF/,"");
 return rows;
}
export function previewBankResults(text:string,lines:BankLine[]){
 const rows=csvRows(text),headers=(rows.shift()||[]).map(h=>h.trim().toLowerCase());
 if(!headers.includes("status")||(!headers.includes("payroll_record_id")&&!headers.includes("employee_id")))throw Error("CSV needs status and payroll_record_id or employee_id columns. Optional columns: reference, failure_reason.");
 if(new Set(headers).size!==headers.length)throw Error("CSV has duplicate column headers");
 if(rows.length>1000)throw Error("Import at most 1,000 bank results per preview");
 const seen=new Set<number>(),valid:{row:number;line:ImportLine;employee_id:number}[]=[],errors:{row:number;error:string}[]=[];
 rows.forEach((values,index)=>{
  const source=Object.fromEntries(headers.map((h,i)=>[h,(values[i]||"").trim()])),row=index+2;
  const matches=source.payroll_record_id?lines.filter(l=>String(l.payroll_record_id)===source.payroll_record_id):lines.filter(l=>String(l.employee_id)===source.employee_id);
  const match=matches[0];let error="";
  if(values.length!==headers.length)error="Column count does not match the header";
  else if(matches.length!==1)error=matches.length?"Employee matches multiple payment lines; use payroll_record_id":"No matching line in this payment batch";
  else if(source.employee_id&&String(match.employee_id)!==source.employee_id)error="Employee ID does not match the payroll record";
  else if(match.status.toLowerCase()==="paid")error="Payment is already recorded Paid; this row cannot overwrite it";
  else if(seen.has(match.payroll_record_id))error="Duplicate payment line in this file";
  const status=source.status?.toLowerCase(),reference=source.reference||source.utr_number||"",failure=source.failure_reason||"";
  if(!error&&!['paid','failed'].includes(status))error="Status must be Paid or Failed";
  if(!error&&status==="paid"&&!reference)error="Paid needs a bank transaction reference";
  if(!error&&status==="failed"&&!failure)error="Failed needs the bank rejection reason";
  if(error){errors.push({row,error});return;}
  seen.add(match.payroll_record_id);
  valid.push({row,employee_id:match.employee_id,line:{payroll_record_id:match.payroll_record_id,payment_status:status==="paid"?"Paid":"Failed",...(status==="paid"?{utr_number:reference}:{failure_reason:failure})}});
 });
 return {valid,errors,total:rows.length};
}
