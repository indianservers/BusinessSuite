import { useBusinessTerms } from '@/hooks/use-business-terms';
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { CompanyProfile } from "@/shared/master-data/CompanySelect";
import Record360Workspace from "./Record360Workspace";
export default function Record360Page(){
  const { term } = useBusinessTerms();
  const {id}=useParams(),location=useLocation(),navigate=useNavigate();
  const source=location.pathname.startsWith('/pms')?'project_management':location.pathname.startsWith('/srm')?'srm':'crm';
  const [showDetails,setShowDetails]=useState(false);
  useEffect(()=>setShowDetails(false),[source,id]);
  if(!id||!/^[1-9]\d*$/.test(id)||!Number.isSafeInteger(Number(id)))return <p role="alert">Choose a valid {term('customer').toLowerCase()}.</p>;
  return <main className="r360-page"><Button variant="ghost" onClick={()=>navigate(-1)}>Back</Button><h1 className="page-title">{term('customer')} 360</h1><Record360Workspace key={`${source}:${id}`} kind="company" id={Number(id)} source={source}/><details open={showDetails} onToggle={event=>setShowDetails(event.currentTarget.open)}><summary>{term('customer')} details &amp; editing</summary>{showDetails&&<CompanyProfile key={`${source}:${id}`} id={Number(id)} source={source} inline onClose={()=>setShowDetails(false)}/>}</details></main>;
}
