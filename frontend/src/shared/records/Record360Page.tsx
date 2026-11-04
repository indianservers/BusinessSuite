import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { CompanyProfile } from "@/shared/master-data/CompanySelect";
export default function Record360Page(){
  const {id}=useParams(),location=useLocation(),navigate=useNavigate();
  const source=location.pathname.startsWith('/pms')?'project_management':location.pathname.startsWith('/srm')?'srm':'crm';
  if(!id||!/^\d+$/.test(id))return <p role="alert">Choose a valid customer.</p>;
  return <main className="r360-page"><Button variant="ghost" onClick={()=>navigate(-1)}>Back</Button><CompanyProfile key={`${source}:${id}`} id={Number(id)} source={source} inline onClose={()=>navigate(-1)}/></main>;
}
