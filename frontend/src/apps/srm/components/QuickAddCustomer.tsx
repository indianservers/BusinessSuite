import { CompanyQuickCreate } from "@/shared/master-data/CompanySelect";
export type PosCustomerRecord = {id:number;name:string;phone?:string|null;phone_country_code?:string|null;email?:string|null;address?:string|null};
export default function QuickAddCustomer({onClose,onCreated}:{onClose:()=>void;onCreated:(customer:PosCustomerRecord)=>void}) {
  return <CompanyQuickCreate source="srm" roles={["Customer"]} recordLabel="customer" defaultEntityKind="Individual" onClose={onClose} onSaved={company=>onCreated(company)}/>;
}
