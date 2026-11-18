import {useAuthStore,type AuthUser} from '@/store/authStore';
import { useLocation } from 'react-router-dom';
import { commonRouteContext } from '@/lib/common-routes';
/** Action affordances follow the active page's module; endpoint permissions stay authoritative. */
export function moduleForActionPath(path:string):string|undefined {
 const common = commonRouteContext(path);
 if(common)return moduleForActionPath(common.nativePath);
 if(path.startsWith('/common/'))return 'unavailable';
 if(path.startsWith('/admin/customization'))return 'customization';
 if(path.startsWith('/ai-agents'))return 'ai';
 for(const [prefix,key]of [['/crm','crm'],['/pms','project_management'],['/hrms','hrms'],['/srm','srm'],['/fam','fam'],['/power-apps','power_apps'],['/analytics','analytics']])if(path===prefix||path.startsWith(prefix+'/'))return key;
}
export function moduleActionAllowed(user:AuthUser|null|undefined,path:string,action:string){
 const module=moduleForActionPath(path);if(!module)return true;
 if(user?.is_superuser)return true;
 if(!user?.access)return false;
 if(!user.access.managed)return true;
 const grant=user.access.grants[module];return !!grant?.enabled&&grant.actions.includes(action);
}
export function useModuleAction(action:string){const user=useAuthStore(s=>s.user);const {pathname}=useLocation();return moduleActionAllowed(user,pathname,action);}
