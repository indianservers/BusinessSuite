import { useLocation } from 'react-router-dom';
import { useCenterScope } from './center/shared';
import Workspace from './WhatsAppCommunicationWorkspace';

export default function WhatsAppCommunicationPage(){
 const scope=useCenterScope(),source=useLocation().pathname.startsWith('/srm')?'srm':'crm';
 return <Workspace key={`${scope}:${source}`} scope={scope} source={source}/>;
}
