import type { CollectionGroupField } from "./GroupedRecords";

/** Only exposes grouping fields actually present in the supplied records. */
export function standardRecordGroups<T>(items: T[]): CollectionGroupField<T>[] {
  const candidates:[string,string,string[]][]=[
    ["status","Status",["status","stage","state"]],
    ["type","Type",["type","kind","entity_type","record_type","file_type","mime_type","field_type","trigger_type"]],
    ["category","Category",["category_name","category","group_name"]],
    ["module","Module",["module_name","module","module_api_name"]],
    ["owner","Owner",["owner_name","assignee_name","employee_name","assigned_to_name"]],
    ["priority","Priority",["priority"]],
    ["project","Project",["project_name"]],
    ["company","Company",["company_name","customer_name"]],
  ];
  const record=(item:T)=>item&&typeof item==="object"?item as Record<string,unknown>:{};
  const scalar=(value:unknown):value is string|number|boolean=>["string","number","boolean"].includes(typeof value);
  const fields:CollectionGroupField<T>[]=[];
  for(const [id,label,keys] of candidates){
    if(!items.some(item=>keys.some(key=>scalar(record(item)[key]))))continue;
    fields.push({id,label,value:item=>{const row=record(item);return keys.map(key=>row[key]).find(value=>scalar(value)&&String(value).trim()!=="");}});
  }
  if(!fields.some(field=>field.id==="status")&&items.some(item=>["is_active","enabled","active","published"].some(key=>typeof record(item)[key]==="boolean"))){
    fields.unshift({id:"status",label:"Status",value:item=>{const row=record(item);const value=["is_active","enabled","active","published"].map(key=>row[key]).find(value=>typeof value==="boolean");return value===undefined?null:value?"Active":"Disabled";}});
  }
  if(items.some(item=>Array.isArray(record(item).tags)||Array.isArray(record(item).labels)))fields.push({id:"tags",label:"Tags",value:item=>record(item).tags||record(item).labels});
  return fields;
}
