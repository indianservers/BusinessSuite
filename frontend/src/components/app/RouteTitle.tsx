import { useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { getRoleNav } from "@/lib/roles";
import { getProductForContext } from "@/lib/products";
import { commonRouteContext } from "@/lib/common-routes";

const suitePages:Record<string,string>={"/":"Business Suite","/dashboard":"Applications","/login":"Sign in","/signup":"Request access","/account":"My account","/help":"Help","/notifications":"Notifications"};
const nativePath=(path:string)=>commonRouteContext(path.split("?")[0])?.nativePath || path.split("?")[0];
/** Supply a title for every route. Page-specific effects can add richer record names. */
export default function RouteTitle() {
  const location=useLocation(),user=useAuthStore(state=>state.user);
  const operation=new URLSearchParams(location.search).get("operation") || location.pathname;
  useLayoutEffect(()=>{
    const path=nativePath(operation),suite=suitePages[location.pathname];
    const entries=suite?[]:getRoleNav(user?.role,user?.is_superuser,location.pathname).map(item=>({...item,path:nativePath(item.to)}));
    const entry=entries.filter(item=>path===item.path || path.startsWith(item.path+"/")).sort((a,b)=>b.path.length-a.path.length)[0];
    const fallback=path.split("/").filter(part=>part && !/^\d+$/.test(part)).pop()?.replace(/[-_]/g," ").replace(/\b\w/g,char=>char.toUpperCase()) || "Workspace";
    const title=suite || (/\/login\/?$/.test(path)?"Sign in":entry?.label || fallback);
    document.title=`${title} - ${suite?"Business Suite":getProductForContext(location.pathname,user?.role,user?.is_superuser).name}`;
  },[location.pathname,operation,user?.role,user?.is_superuser]);
  return null;
}
