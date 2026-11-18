import { collectionDefinition } from "./collection-definitions";
import type { GridColumn } from "./types";
import type { CollectionGroupField } from "./GroupedRecords";
import { percentage } from "./collection-model";
import { columnValue } from "./column-presentation";

/** Only known display fields become columns; arbitrary API properties are never exposed. */
export function collectionColumns<T>(items: T[], fields: CollectionGroupField<T>[], scope = ""): GridColumn<T>[] {
  const row = (item:T):Record<string,unknown> => item && typeof item === "object" ? item as Record<string,unknown> : {};
  const definition = collectionDefinition(scope);
  const entity = definition.entity;
  const candidates: [string,string,string[]][] = [
    ["name",entity,["name","title","full_name","employee_name","customer_name","module_label","field_label","display_name","rule_key","metric_key","feature_key","key_prefix","report_id","invoice_number","quote_number"]],
    ["code","Code",["code","employee_code","asset_tag","sku","invoice_number","quote_number"]],
    ["status","Status",["status","state"]], ["stage","Stage",["stage_name","stage"]],
    ["priority","Priority",["priority"]], ["company","Company",["company_name"]],
    ["owner","Owner",["owner_name","assigned_to_name"]], ["department","Department",["department_name"]],
    ["type","Type",["type","record_type","employment_type"]], ["category","Category",["category_name"]],
    ["currency","Currency",["currency","currency_code"]], ["amount","Amount",["amount","total_amount"]],
    ["balance","Balance",["balance","outstanding_amount"]], ["quantity","Quantity",["quantity","stock_quantity"]],
    ["progress","Progress",["progress_percent","completion_percentage","completion_percent","completionPercent","progress"]],
    ["start","Start date",["start_date","startDate","from_date","period_start"]],
    ["due","Due date",["due_date","dueDate","end_date","endDate","to_date","period_end"]],
    ["created","Created",["created_at"]], ["updated","Updated",["updated_at"]],
    ["plan_type","Plan type",["plan_type"]], ["provider","Provider",["provider_name"]],
    ["employer_contribution","Employer contribution",["employer_contribution"]], ["employee_contribution","Employee contribution",["employee_contribution"]],
    ["claim_type","Claim type",["claim_type"]], ["approved_amount","Approved amount",["approved_amount"]], ["expense_date","Expense date",["expense_date"]], ["exit_type","Exit type",["exit_type"]], ["claim_amount","Claim amount",["claim_amount"]],
    ["delivery_mode","Delivery mode",["delivery_mode"]], ["duration","Duration (hours)",["duration_hours"]],
    ["enrolled","Enrolled",["enrolled_count","enrollment_count"]], ["channel","Channel",["channel"]],
    ["method","HTTP method",["method","http_method"]], ["path","API path",["path","endpoint"]],
    ["response_code","Response code",["status_code","response_code"]], ["duration_ms","Duration (ms)",["duration_ms"]],
    ["next_run","Next run",["next_run_at"]], ["request_type","Request type",["request_type"]],
    ["requested_by","Requested by",["requested_by_name"]], ["version","Version",["version"]],
    ["expected_start","Expected start date",["expected_start_date"]], ["expected_end","Expected end date",["expected_end_date","expected_completion_date"]],
    ["planned_start","Planned start date",["planned_start_date"]], ["planned_end","Planned end date",["planned_end_date"]],
    ["assigned_date","Assigned date",["assigned_date"]], ["returned_date","Returned date",["returned_date"]],
    ["resignation_date","Resignation date",["resignation_date"]], ["last_working_date","Last working date",["last_working_date"]],
    ["employee_id","Employee ID",["employee_id"]], ["event","Event",["event_type","action"]],
    ["module","Module",["module_name","module_api_name"]], ["resource","Resource",["resource_name"]],
    ["plan","Plan",["plan_name"]], ["course","Course",["course_name"]], ["job","Job title",["job_title"]],
    ["workflow","Workflow",["workflow_name"]], ["template","Template",["template_name"]],
  ];
  const columns:GridColumn<T>[]=[];
  if(items.some(item=>row(item).first_name)) columns.push({id:"person",title:"Employee",accessor:item=>[row(item).first_name,row(item).last_name].filter(Boolean).join(" "),width:220});
  for(const [id,title,keys] of candidates){
    if(!definition.columns.includes(id)&&!items.some(item=>keys.some(key=>typeof row(item)[key]==="string"||typeof row(item)[key]==="number")))continue;
    const value=(item:T)=>keys.map(key=>row(item)[key]).find(value=>typeof value==="number"||typeof value==="string"&&value.trim()!=="");
    columns.push({id,title:/benefits/i.test(scope)&&["employer_contribution","employee_contribution","claim_amount"].includes(id)?`${title} (INR)`:title,accessor:value,width:id==="name"?220:140,...(id==="progress"?{render:(item:T)=>{const progress=percentage(value(item));return progress===undefined?"—":columnValue("Progress",`${progress}%`);}}:{})});
  }
  for(const field of fields){
    const existing=columns.findIndex(column=>column.id===field.id||column.title===field.label);
    const column:GridColumn<T>={id:field.id,title:field.label,accessor:item=>{const value=field.value(item);return Array.isArray(value)?value.join(", "):value;}};
    if(existing>=0)columns[existing]={...columns[existing],...column};else columns.push(column);
  }
  return columns;
}
