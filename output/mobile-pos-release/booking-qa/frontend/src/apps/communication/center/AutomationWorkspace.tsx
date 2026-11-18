import { Link } from 'react-router-dom';
import { Workflow, History, Zap, ArrowDown, Clock3, Send } from 'lucide-react';
import CustomerCommunications from '../CustomerCommunications';
import { canAccessRoute } from '@/lib/roles';
import { useAuthStore } from '@/store/authStore';

export default function AutomationWorkspace(){
  const user=useAuthStore(s=>s.user);
  const allowed=canAccessRoute('/power-apps/automations/new',user?.role,user?.is_superuser);
  return <section className="cc-automation-workspace"><div className="cc-section-title"><div><h2>Communication automations</h2><p>Manage existing customer rules or build a workflow in Business Suite Automations.</p></div><div className="cc-toolbar">{allowed&&<><Link className="cc-link-button" to="/power-apps/automations/new"><Workflow size={15}/>Visual workflow builder</Link><Link className="cc-link-button" to="/power-apps/automations/executions"><History size={15}/>Execution history</Link></>}</div></div><div className="cc-workflow-guide" aria-label="Communication workflow stages">{[{icon:Zap,title:'Trigger',text:'CRM event or scheduled date'},{icon:Clock3,title:'Conditions & timing',text:'Eligible audience and configured delay'},{icon:Send,title:'Deliver & track',text:'Approved message and delivery evidence'}].map(({icon:Icon,title,text},index)=><div key={title}><span>{index+1}</span><Icon size={20}/><strong>{title}</strong><small>{text}</small>{index<2&&<ArrowDown size={15}/>}</div>)}</div><CustomerCommunications initialTab="automations"/></section>;
}
