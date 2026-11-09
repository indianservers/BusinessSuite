import {test} from "../frontend/node_modules/playwright/test";
/** Expand the visible group itself, including nested groups, without closing menus. */
export async function installGridExpansion(page:any){
  if(page._creationGridExpansion)return;
  page._creationGridExpansion=true;
  await page.addLocatorHandler(page.locator('body:not(:has([role="dialog"], [role="menu"], [aria-haspopup="menu"][aria-expanded="true"])) .udg-group-row button[aria-expanded="false"]').first(),async(group:any)=>{
    const button=await group.elementHandle();
    await group.click();
    if(button)await page.waitForFunction((node:HTMLElement)=>!node.isConnected||node.getAttribute('aria-expanded')==='true',button);
  },{noWaitAfter:true});
}
/** Use a real managed actor in native pages while keeping administrator fixture setup separate. */
export async function installNativeActor(page:any,request:any,base:string,fixtureAuth:any,preserveSession=false,profileOverride?:string|null){
  await installGridExpansion(page);
  const info:any=test.info();
  info._nativeRoutes ||= new Set<string>();info._nativeWrites ||= [];
  page.on('framenavigated',(frame:any)=>{if(frame===page.mainFrame()){try{info.annotations.push({type:'native-page',description:new URL(frame.url()).pathname});}catch{}}});
  page.on('response',(response:any)=>{const req=response.request();if(!['POST','PUT','PATCH','DELETE'].includes(req.method()))return;const path=new URL(response.url()).pathname;if(!path.startsWith('/api/v1/')||/\/(auth|access|notifications|realtime)\//.test(path))return;info.annotations.push({type:'native-write',description:JSON.stringify({page:new URL(page.url()).pathname,path,method:req.method(),status:response.status()})});});
  let actor=fixtureAuth;
  const profile=profileOverride===undefined?process.env.CRUD121_UI_ROLE:profileOverride;
  if(profile && fixtureAuth.is_superuser){
    const login=await request.post(base+'/api/v1/auth/login',{data:{email:`conditional-${profile}@suiteqa.example.com`,password:'ConditionalQA@12345'}});
    if(!login.ok())throw Error('Managed UI actor login failed: '+login.status());
    actor=await login.json();
  }
  const effective=await request.get(base+'/api/v1/access/me',{headers:{Authorization:'Bearer '+actor.access_token}});
  if(!effective.ok())throw Error('Managed UI actor policy failed: '+effective.status());
  actor.access=await effective.json();
  info.annotations.push({type:"native-actor",description:JSON.stringify({userId:actor.user_id,email:actor.email,isSuperuser:actor.is_superuser})});
  page._nativeActor=actor;
  await page.addInitScript(({actor,preserveSession}:any)=>{
    if(preserveSession && sessionStorage.getItem('hrms-auth'))return;
    sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:actor.access_token,refreshToken:actor.refresh_token,user:{id:actor.user_id,email:actor.email,role:actor.role,is_superuser:actor.is_superuser,employee_id:actor.employee_id,access:actor.access},isAuthenticated:true},version:0}));
  },{actor,preserveSession});
  if(process.env.CREATION_RESPONSE_TIMEOUT)page.setDefaultTimeout(Number(process.env.CREATION_RESPONSE_TIMEOUT));
  return actor;
}
