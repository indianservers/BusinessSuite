import {test,expect} from "../frontend/node_modules/playwright/test";
import {installNativeActor} from "./crud121-ui-actor";
const BASE=process.env.PLAYWRIGHT_BASE_URL||'http://127.0.0.1:1582';test.setTimeout(180000);
for(const route of ["/pms/messages","/crm/messages"])test(route+" create-only author sends without edit or delete controls",async({page,request})=>{
 const r=await request.post(BASE+"/api/v1/auth/login",{data:{email:"conditional-creator@suiteqa.example.com",password:"ConditionalQA@12345"}});expect(r.ok()).toBeTruthy();await installNativeActor(page,request,BASE,await r.json());page.setDefaultTimeout(45000);const tag=String(Date.now()),body="Role-only self message "+tag;await page.goto(BASE+route+"?workspace=1");await page.getByRole("button",{name:"+ New conversation",exact:true}).click();const d=page.getByRole("dialog",{name:"New conversation",exact:true});await d.locator("label").filter({hasText:/^Type/}).locator("select").selectOption("channel");await d.getByLabel("Name",{exact:true}).fill("Role private "+tag);let pending=page.waitForResponse(r=>r.url().includes("/chat/conversations")&&r.request().method()==="POST");await d.getByRole("button",{name:"Create conversation",exact:true}).click();let response=await pending;expect(response.ok(),await response.text()).toBeTruthy();await page.getByRole("textbox",{name:"Message",exact:true}).fill(body);pending=page.waitForResponse(r=>/\/messages$/.test(r.url())&&r.request().method()==="POST");await page.getByRole("button",{name:"Send",exact:true}).click();response=await pending;expect(response.ok(),await response.text()).toBeTruthy();const message=await response.json(),article=page.locator("#chat-"+message.id);await expect(article).toBeVisible({timeout:45000});await expect(article.getByRole("button",{name:"Edit",exact:true})).toHaveCount(0);await expect(article.getByRole("button",{name:"Delete",exact:true})).toHaveCount(0);
});

for(const route of ["/pms/messages","/crm/messages"])for(const role of ["editor","deleter"])test(route+" "+role+" own-message action isolation",async({page,request})=>{
 const login=async(email:string,password:string)=>{const r=await request.post(BASE+"/api/v1/auth/login",{data:{email,password}});expect(r.ok()).toBeTruthy();return r.json();};
 const auth=await login("conditional-"+role+"@suiteqa.example.com","ConditionalQA@12345");
 await installNativeActor(page,request,BASE,auth);page.setDefaultTimeout(45000);
 const actor=(page as any)._nativeActor;
 const admin=await login("admin@suiteqa.example.com","SuiteQA@12345");
 const fixture=await request.post(BASE+"/api/v1/collaboration/_acceptance/chat",{headers:{Authorization:"Bearer "+admin.access_token},params:{owner_id:actor.user_id,workspace_id:1}});expect(fixture.ok(),await fixture.text()).toBeTruthy();const room=await fixture.json();
 await page.goto(BASE+route+"?workspace=1&conversation="+room.conversation_id);
 const article=page.locator("#chat-"+room.message_id);await expect(article).toBeVisible({timeout:45000});
 await expect(page.getByRole("button",{name:"+ New conversation",exact:true})).toBeDisabled();
 await expect(page.getByRole("textbox",{name:"Message",exact:true})).toHaveCount(0);
 if(role==="editor"){
   await expect(article.getByRole("button",{name:"Delete",exact:true})).toHaveCount(0);
   await article.getByRole("button",{name:"Edit",exact:true}).click();
   await page.getByRole("textbox",{name:"Edit message text",exact:true}).fill(room.body+" edited");
   const writing=page.waitForResponse(r=>r.url().endsWith("/messages/"+room.message_id)&&r.request().method()==="PATCH");
   await page.getByRole("button",{name:"Save edit",exact:true}).click();const result=await writing;expect(result.ok(),await result.text()).toBeTruthy();await expect(article).toContainText(room.body+" edited");
 }else{
   await expect(article.getByRole("button",{name:"Edit",exact:true})).toHaveCount(0);
   await article.getByRole("button",{name:"Delete",exact:true}).click();
   const writing=page.waitForResponse(r=>r.url().endsWith("/messages/"+room.message_id)&&r.request().method()==="DELETE");
   await page.getByRole("dialog").getByRole("button",{name:"Delete message",exact:true}).click();const result=await writing;expect(result.ok(),await result.text()).toBeTruthy();await expect(article).toContainText("Message deleted");
 }
 // Reading and personal bookmarks remain available without content mutation authority.
 if(role==="editor"){
   await article.locator("summary[aria-label='Message actions']").click();
   const writing=page.waitForResponse(r=>r.url().endsWith("/messages/"+room.message_id+"/saved")&&r.request().method()==="PUT");
   await page.getByRole("button",{name:"Save message",exact:true}).click();expect((await writing).ok()).toBeTruthy();
   await page.keyboard.press("Escape");
   await page.getByRole("tab",{name:"Follow-ups",exact:false}).click();
   const status=page.getByLabel("Status for "+room.followup_title,{exact:true}).first();
   await expect(status).toBeEnabled({timeout:45000});
   for(const state of ["In Progress","Completed"]){
     const changing=page.waitForResponse(r=>r.url().endsWith("/followups/"+room.followup_id)&&r.request().method()==="PATCH");
     await status.selectOption(state);const result=await changing;expect(result.ok(),await result.text()).toBeTruthy();
     await expect(status).toBeEnabled({timeout:45000});await expect(status).toHaveValue(state);
   }
   await page.reload();await page.getByRole("tab",{name:"Follow-ups",exact:false}).click();
   await expect(page.getByLabel("Status for "+room.followup_title,{exact:true}).first()).toHaveValue("Completed",{timeout:45000});
 }
 if(role==="deleter"){const denied=await request.patch(BASE+"/api/v1/collaboration/workspaces/1/chat/conversations/"+room.conversation_id+"/messages/"+room.message_id,{headers:{Authorization:"Bearer "+auth.access_token},data:{body:"Denied unauthorized edit"}});
 expect(denied.status()).toBe(403);}
});
