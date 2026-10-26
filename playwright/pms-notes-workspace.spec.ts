import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
const base="/api/v1/project-management";
async function login(page:Page,email="notes-admin@example.com"){
  const response=await page.request.post("/api/v1/auth/login",{data:{email,password:"NotesQA@123",module:"project_management"}});
  expect(response.ok()).toBeTruthy();const auth=await response.json();
  await page.addInitScript(auth=>{window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};localStorage.setItem("hrms-auth",JSON.stringify({state:{accessToken:auth.access_token,refreshToken:auth.refresh_token,user:{id:auth.user_id,email:auth.email,role:auth.role,is_superuser:auth.is_superuser},isAuthenticated:true},version:0}));},auth);
  return {Authorization:`Bearer ${auth.access_token}`};
}
async function create(page:Page,headers:Record<string,string>,title:string,extra:Record<string,unknown>={}){
  const response=await page.request.post(base+"/notes",{headers,data:{title,content:"Existing text",...extra}});expect(response.status()).toBe(201);return response.json();
}
async function open(page:Page,id:number){await page.goto(`/pms/notes?note=${id}`);await expect(page.getByRole("textbox",{name:"Note content",exact:true})).toBeVisible();}
async function saved(page:Page,id:number,title?:string){await expect.poll(async()=>{const raw=await page.evaluate(()=>JSON.parse(sessionStorage.getItem("hrms-auth")!).state.accessToken);const data=await(await page.request.get(base+`/notes/${id}`,{headers:{Authorization:`Bearer ${raw}`}})).json();return title?data.title:data.content;}).toContain(title||"suite-richtext");}

test("three-panel workspace loads real projects, tasks and legacy notes",async({page},info)=>{
  await page.setViewportSize({width:1680,height:1050});const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));await login(page);await page.goto("/pms/notes?note=1");
  await expect(page.getByRole("textbox",{name:"Note title",exact:true})).toHaveValue("API Documentation");
  await expect(page.getByRole("heading",{name:"Overview",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Expand Website Development",exact:true}).click();
  await page.getByRole("button",{name:"Expand Tasks",exact:true}).click();
  await page.getByRole("button",{name:"Expand API Integration",exact:true}).click();
  await expect(page.getByRole("treeitem",{name:/Review API contract/})).toBeVisible();
  await expect(page.getByRole("treeitem",{name:/Reference/})).toBeVisible();
  await page.screenshot({path:info.outputPath("notes-desktop.png"),animations:"disabled"});
  await page.getByRole("button",{name:"Collapse API Integration",exact:true}).click();
  await page.reload();await expect(page.getByRole("button",{name:"Expand API Integration",exact:true})).toBeVisible();
  await page.getByLabel("Explorer options",{exact:true}).click();await page.getByRole("button",{name:"Expand all",exact:true}).click();await expect(page.getByRole("button",{name:"Collapse Review API contract",exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});

test("create a private note, format it, autosave and reload without repeated conversion",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Autosave source");await open(page,note.id);
  await page.getByRole("textbox",{name:"Note title",exact:true}).fill("Autosave verified");
  const editor=page.getByRole("textbox",{name:"Note content",exact:true});await editor.fill("Formatted words");await editor.press("Control+a");
  await page.getByRole("button",{name:"Bold (Ctrl+B)",exact:true}).click();
  await expect(editor.locator("strong")).toHaveText("Formatted words");await saved(page,note.id,"Autosave verified");
  await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).content).toContain("<strong>");
  const version=(await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).version;
  await page.reload();await expect(editor.locator("strong")).toHaveText("Formatted words");
  await expect(page.getByRole("status").filter({hasText:"Saved"})).toBeVisible();
  expect((await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).version).toBe(version);
});

test("nested folders, contextual creation and bulk moves use the real API",async({page})=>{
  const suffix=Date.now();const parentName=`QA Ideas ${suffix}`,childName=`Nested Research ${suffix}`;const headers=await login(page);await page.goto("/pms/notes");await expect(page.getByRole("textbox",{name:"Note content",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Actions for Personal Notes",exact:true}).click();await page.getByRole("menuitem",{name:"New folder",exact:true}).click();
  await page.getByLabel("Folder name",{exact:true}).fill(parentName);await page.getByRole("button",{name:"Save folder",exact:true}).click();
  await expect(page.getByRole("treeitem",{name:new RegExp(parentName)})).toBeVisible();
  await page.getByRole("button",{name:`Actions for ${parentName}`,exact:true}).click();await page.getByRole("menuitem",{name:"New folder",exact:true}).click();
  await page.getByLabel("Folder name",{exact:true}).fill(childName);await page.getByRole("button",{name:"Save folder",exact:true}).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const folders=await(await page.request.get(base+"/note-folders",{headers})).json();const child=folders.find((f:any)=>f.name===childName);const parent=folders.find((f:any)=>f.name===parentName);expect(child.parent_id).toBe(parent.id);
  const note=await create(page,headers,`Move this real note ${suffix}`);await open(page,note.id);
  await page.getByRole("checkbox",{name:`Select Move this real note ${suffix}`,exact:true}).check();await page.getByRole("button",{name:"Move selected notes",exact:true}).click();
  await page.getByLabel("Move destination").selectOption(`folder:${child.id}`);await page.getByRole("button",{name:"Move notes",exact:true}).click();
  await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).folder_id).toBe(child.id);
});

test("tables, headings, links, slash commands and find-replace persist",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Editor tools");await open(page,note.id);const editor=page.getByRole("textbox",{name:"Note content",exact:true});
  await editor.fill("Heading text");await editor.press("Control+a");await page.getByLabel("Paragraph style",{exact:true}).selectOption("6");await expect(editor.locator("h6")).toHaveText("Heading text");
  await editor.press("Control+End");await editor.press("Enter");await page.getByLabel("Paragraph style",{exact:true}).selectOption("p");await editor.pressSequentially("Findable word");
  await page.getByRole("button",{name:"Insert table",exact:true}).click();await expect(editor.locator("table")).toBeVisible();
  await page.getByRole("button",{name:"Add row",exact:true}).click();await expect(editor.locator("table tr")).toHaveCount(4);
  await page.getByRole("button",{name:"Remove table",exact:true}).click();await expect(editor.locator("table")).toHaveCount(0);
  await page.getByLabel("More formatting",{exact:true}).click();await page.getByRole("button",{name:"Find and replace",exact:true}).click();
  await page.getByLabel("Find in note").fill("Findable");await page.getByLabel("Replace with").fill("Replaced");await page.getByRole("button",{name:"Replace all",exact:true}).click();await expect(editor).toContainText("Replaced word");
  await page.getByLabel("Close find",{exact:true}).click();await editor.press("Control+End");await editor.press("Enter");await editor.pressSequentially("/call");
  await expect(page.getByRole("menu",{name:"Insert block",exact:true})).toBeVisible();await page.getByRole("menuitem",{name:"Callout",exact:true}).click();await expect(editor.locator("blockquote")).toBeVisible();
  await saved(page,note.id);
});

test("private images upload securely, render inline and survive a reload",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Private inline image");await open(page,note.id);
  await page.getByLabel("Insert private image",{exact:true}).setInputFiles({name:"diagram.png",mimeType:"image/png",buffer:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5k0AAAAASUVORK5CYII=","base64")});
  await expect(page.locator(".note-inline-image img")).toBeVisible();
  await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).content).toContain("data-note-image");
  await page.reload();await expect(page.locator(".note-inline-image img")).toBeVisible();
});

test("sharing is explicit and revocable; other users cannot edit or discover private notes",async({page,browser})=>{
  const headers=await login(page);const note=await create(page,headers,"Sharing boundary verified");await open(page,note.id);
  const reader=await browser.newPage();const readerHeaders=await login(reader,"notes-reader@example.com");
  expect((await reader.request.get(base+`/notes/${note.id}`,{headers:readerHeaders})).status()).toBe(404);
  await page.getByRole("button",{name:"Share",exact:true}).click();await page.getByLabel("Share with colleague email").fill("notes-reader@example.com");await page.getByRole("button",{name:"Invite to read",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("notes-reader@example.com");await open(reader,note.id);await expect(reader.getByRole("textbox",{name:"Note title",exact:true})).toBeDisabled();
  expect((await reader.request.put(base+`/notes/${note.id}`,{headers:readerHeaders,data:{title:"Not allowed",version:1}})).status()).toBe(404);
  await page.getByRole("button",{name:"Revoke access",exact:true}).click();await expect.poll(async()=> (await reader.request.get(base+`/notes/${note.id}`,{headers:readerHeaders})).status()).toBe(404);await reader.close();
});

test("archive, trash, restore, history, PDF export and mobile navigation",async({page},info)=>{
  const headers=await login(page);const note=await create(page,headers,"Lifecycle verified");await open(page,note.id);
  await page.getByRole("textbox",{name:"Note title",exact:true}).fill("Lifecycle revised");await saved(page,note.id,"Lifecycle revised");
  await page.getByLabel("More note actions",{exact:true}).click();await page.getByRole("button",{name:"Version history",exact:true}).click();await expect(page.getByRole("dialog")).toContainText("Lifecycle verified");await page.getByRole("button",{name:"Close dialog",exact:true}).click();
  await page.getByLabel("More note actions",{exact:true}).click();const download=page.waitForEvent("download");await page.getByRole("button",{name:"Export PDF",exact:true}).click();expect((await download).suggestedFilename()).toContain(".pdf");
  const exported=await page.request.get(base+`/notes/${note.id}/export.pdf`,{headers});expect((await exported.body()).subarray(0,4).toString()).toBe("%PDF");
  await page.getByLabel("More note actions",{exact:true}).click();await page.getByRole("button",{name:"Archive note",exact:true}).click();await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).archived).toBe(true);
  await page.setViewportSize({width:390,height:844});await page.getByRole("navigation",{name:"Notes mobile navigation"}).getByRole("button",{name:"Folders",exact:true}).click();await expect(page.getByRole("tree",{name:"Note folders",exact:true})).toBeVisible();
  await page.getByRole("treeitem",{name:"Archived",exact:true}).click();await expect(page.getByRole("region",{name:"Note list",exact:true})).toBeVisible();await page.getByRole("button",{name:/Lifecycle revised/}).click();
  await page.screenshot({path:info.outputPath("notes-mobile.png"),animations:"disabled"});
  await page.getByLabel("More note actions",{exact:true}).click();page.once("dialog",dialog=>dialog.accept());await page.getByRole("button",{name:"Move to Trash",exact:true}).click();await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).deleted_at).not.toBeNull();
  await page.getByRole("button",{name:"Restore note",exact:true}).click();await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).deleted_at).toBeNull();
});

test("contextual personal, project and task notes save the correct associations",async({page})=>{
  const headers=await login(page);await page.goto("/pms/notes");await expect(page.getByRole("textbox",{name:"Note content",exact:true})).toBeVisible();await expect(page.getByRole("status").filter({hasText:"Saved"})).toBeVisible();
  await page.getByRole("button",{name:"Actions for Personal Notes",exact:true}).click();await page.getByRole("menuitem",{name:"New note",exact:true}).click();
  const title=page.getByRole("textbox",{name:"Note title",exact:true});await title.fill("Created personally");await expect(page).toHaveURL(/note=\d+/);
  let id=Number(new URL(page.url()).searchParams.get("note"));let row=await(await page.request.get(base+`/notes/${id}`,{headers})).json();expect(row.project_id).toBeNull();expect(row.visibility).toBe("private");
  await page.getByRole("button",{name:"Actions for Website Development",exact:true}).click();await page.getByRole("menuitem",{name:"New note",exact:true}).click();await title.fill("Created in project");await expect(page).toHaveURL(/note=\d+/);
  id=Number(new URL(page.url()).searchParams.get("note"));row=await(await page.request.get(base+`/notes/${id}`,{headers})).json();expect(row.project_id).toBe(1);expect(row.task_id).toBeNull();
  await page.getByRole("button",{name:"Expand Website Development",exact:true}).click();await page.getByRole("button",{name:"Expand Tasks",exact:true}).click();await page.getByRole("button",{name:"Actions for API Integration",exact:true}).click();await page.getByRole("menuitem",{name:"New note",exact:true}).click();await title.fill("Created on task");await expect(page).toHaveURL(/note=\d+/);
  id=Number(new URL(page.url()).searchParams.get("note"));row=await(await page.request.get(base+`/notes/${id}`,{headers})).json();expect(row.task_id).toBe(1);expect(row.project_id).toBe(1);
});

test("failed save keeps a recoverable draft and a version conflict never overwrites newer content",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Recovery source");await open(page,note.id);
  const current=await(await page.request.get(base+`/notes/${note.id}`,{headers})).json();
  const {id,version,title,content,project_id,task_id,folder_id,tags,pinned,favorite,archived}=current;
  expect((await page.request.put(base+`/notes/${id}`,{headers,data:{version,title:"Newer server title",content,project_id,task_id,folder_id,tags,pinned,favorite,archived}})).ok()).toBeTruthy();
  await page.getByRole("textbox",{name:"Note title",exact:true}).fill("Unsaved recovered title");await expect(page.getByRole("alert")).toContainText("another tab");
  expect((await(await page.request.get(base+`/notes/${id}`,{headers})).json()).title).toBe("Newer server title");
  page.once("dialog",d=>d.accept());await page.reload();await expect(page.getByRole("button",{name:"Recover draft",exact:true})).toBeVisible();await page.getByRole("button",{name:"Recover draft",exact:true}).click();await saved(page,id,"Unsaved recovered title");
});

test("search, favorites and browser back-forward preserve real note selection",async({page})=>{
  const headers=await login(page);const stamp=Date.now();const first=await create(page,headers,`Search first ${stamp}`,{tags:[`tag${stamp}`]});const second=await create(page,headers,`Search second ${stamp}`);await open(page,first.id);
  await page.getByRole("button",{name:"Favorite note",exact:true}).click();await expect.poll(async()=> (await(await page.request.get(base+`/notes/${first.id}`,{headers})).json()).favorite).toBe(true);
  await page.getByRole("textbox",{name:"Search notes",exact:true}).fill(`tag${stamp}`);await expect(page.locator(".notes-card")).toHaveCount(1);await page.getByRole("textbox",{name:"Search notes",exact:true}).fill(`Search second ${stamp}`);
  await page.getByRole("button",{name:new RegExp(`Search second ${stamp}`)}).click();await expect(page.getByRole("textbox",{name:"Note title",exact:true})).toHaveValue(second.title);
  await expect(page.getByRole("status").filter({hasText:"Saved"})).toBeVisible();await page.goBack();await expect(page.getByRole("textbox",{name:"Note title",exact:true})).toHaveValue(first.title);await page.goForward();await expect(page.getByRole("textbox",{name:"Note title",exact:true})).toHaveValue(second.title);
});

test("icon formatting applies immediately and persists without Markdown typing",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Toolbar verification");await open(page,note.id);const editor=page.getByRole("textbox",{name:"Note content",exact:true});await editor.fill("Styled selection");await editor.press("Control+a");
  for(const name of ["Bold (Ctrl+B)","Italic (Ctrl+I)","Underline (Ctrl+U)","Strikethrough"])await page.getByRole("button",{name,exact:true}).click();
  for(const tag of ["strong","em","u","s"])await expect(editor.locator(tag)).toHaveText("Styled selection");await page.getByLabel("Font size",{exact:true}).selectOption("20px");await expect(editor.locator('[style*="20px"]')).toBeVisible();
  for(const level of [1,2,3,4,5,6]){await page.getByLabel("Paragraph style",{exact:true}).selectOption(String(level));await expect(editor.locator(`h${level}`).filter({hasText:"Styled selection"})).toHaveText("Styled selection");}
  await page.getByRole("button",{name:"Insert or edit link",exact:true}).click();await page.getByRole("textbox",{name:"Link URL",exact:true}).fill("https://example.com/documentation");await page.getByRole("button",{name:"Apply link",exact:true}).click();await expect(editor.locator("a")).toHaveAttribute("href","https://example.com/documentation");
  await page.getByLabel("More formatting",{exact:true}).click();await page.getByRole("button",{name:"Align center",exact:true}).click();await expect(editor.locator('h6').filter({hasText:'Styled selection'})).toHaveAttribute("style",/text-align: center/);
  await page.getByLabel("More formatting",{exact:true}).click();await page.getByRole("button",{name:"Clear formatting",exact:true}).click();await expect(editor.locator("strong")).toHaveCount(0);
  await page.getByRole("button",{name:"Checklist",exact:true}).click();await expect(editor.locator('ul[data-type="taskList"]')).toBeVisible();await page.getByRole("button",{name:"Checklist",exact:true}).click();await page.getByRole("button",{name:"Bulleted list",exact:true}).click();await expect(editor.locator("ul")).toBeVisible();await page.getByRole("button",{name:"Bulleted list",exact:true}).click();await page.getByRole("button",{name:"Numbered list",exact:true}).click();await expect(editor.locator("ol")).toBeVisible();
  await page.getByRole("button",{name:"Full-screen focus mode",exact:true}).click();await expect(page.locator(".note-writer-fullscreen")).toBeVisible();await page.getByRole("button",{name:"Exit focus mode",exact:true}).click();await saved(page,note.id);
  await page.reload();await expect(editor.locator("ol")).toBeVisible();
});

test("click and drag reorders complete blocks and saves the new order",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Drag blocks verified");await open(page,note.id);const editor=page.getByRole("textbox",{name:"Note content",exact:true});
  await editor.fill("First block");await editor.press("Control+End");await editor.press("Enter");await editor.pressSequentially("Second block");await editor.press("Enter");await editor.pressSequentially("Third block");
  const first=editor.locator("p").nth(0),last=editor.locator("p").nth(2);await first.hover();const handle=page.getByRole("button",{name:"Drag block to reorder",exact:true});await expect(handle).toBeVisible();
  const source=(await handle.boundingBox())!,target=(await last.boundingBox())!;await page.mouse.move(source.x+source.width/2,source.y+source.height/2);await page.mouse.down();await page.mouse.move(source.x+source.width/2+12,source.y+source.height/2,{steps:5});await page.mouse.move(target.x+40,target.y+target.height-2,{steps:15});await expect(page.locator(".note-block-insertion")).toBeVisible();await page.mouse.up();
  await expect(editor.locator("p")).toHaveText(["Second block","Third block","First block"]);await saved(page,note.id);await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).content).toMatch(/Second block.*Third block.*First block/);await page.reload();await expect(editor.locator("p")).toHaveText(["Second block","Third block","First block"]);
});

test("drag a note into a folder and reorder folders with visible drop positions",async({page})=>{
  const headers=await login(page),stamp=Date.now();const folder=await(await page.request.post(base+"/note-folders",{headers,data:{name:`Drag destination ${stamp}`}})).json();const sibling=await(await page.request.post(base+"/note-folders",{headers,data:{name:`Drag sibling ${stamp}`,position:100}})).json();const note=await create(page,headers,`Drag card ${stamp}`);await open(page,note.id);
  const card=page.locator(".notes-card").filter({hasText:note.title});const target=page.locator(".ne-row").filter({has:page.getByRole("treeitem",{name:new RegExp(folder.name)})});await card.dragTo(target);await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).folder_id).toBe(folder.id);
  const from=page.getByRole("treeitem",{name:new RegExp(sibling.name)});const rect=(await target.boundingBox())!;await from.dragTo(target,{targetPosition:{x:rect.width/2,y:2}});
  await expect.poll(async()=>{const rows=await(await page.request.get(base+"/note-folders",{headers})).json();return rows.find((f:any)=>f.id===sibling.id).position<rows.find((f:any)=>f.id===folder.id).position;}).toBe(true);
});

test("drop an image into a blank note and drop a document as a protected attachment",async({page})=>{
  const headers=await login(page);await page.goto("/pms/notes");await expect(page.getByRole("status").filter({hasText:"Saved"})).toBeVisible();await page.getByRole("button",{name:"Actions for Personal Notes",exact:true}).click();await page.getByRole("menuitem",{name:"New note",exact:true}).click();await expect(page.getByRole("textbox",{name:"Note title",exact:true})).toHaveValue("");
  const editor=page.getByRole("textbox",{name:"Note content",exact:true});const image=await page.evaluateHandle(bytes=>{const transfer=new DataTransfer();transfer.items.add(new File([new Uint8Array(bytes)],"drop-diagram.png",{type:"image/png"}));return transfer;},Array.from(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5k0AAAAASUVORK5CYII=","base64")));await editor.dispatchEvent("drop",{dataTransfer:image});await expect(page).toHaveURL(/note=\d+/);const id=Number(new URL(page.url()).searchParams.get("note"));await expect(page.locator(".note-inline-image img")).toBeVisible();await expect.poll(async()=> (await(await page.request.get(base+`/notes/${id}`,{headers})).json()).content).toContain("data-note-image");
  const document=await page.evaluateHandle(()=>{const transfer=new DataTransfer();transfer.items.add(new File(["Protected document body"],"drop-document.txt",{type:"text/plain"}));return transfer;});await editor.dispatchEvent("drop",{dataTransfer:document});await expect(page.locator(".note-attachment-row").filter({hasText:"drop-document.txt"})).toBeVisible();await image.dispose();await document.dispose();
});

test("Undo reverses archive, move and Trash while preserving note content",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Undo verified");const folder=await(await page.request.post(base+"/note-folders",{headers,data:{name:`Undo folder ${Date.now()}`}})).json();await open(page,note.id);
  const get=async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json());
  await page.getByLabel("More note actions",{exact:true}).click();await page.getByRole("button",{name:"Archive note",exact:true}).click();await expect.poll(async()=> (await get()).archived).toBe(true);await page.getByRole("region",{name:"Last note action",exact:true}).getByRole("button",{name:"Undo",exact:true}).click();await expect.poll(async()=> (await get()).archived).toBe(false);
  await page.getByLabel("More note actions",{exact:true}).click();await page.getByRole("button",{name:"Move note",exact:true}).click();await page.getByLabel("Move destination").selectOption(`folder:${folder.id}`);await page.getByRole("button",{name:"Move notes",exact:true}).click();await expect.poll(async()=> (await get()).folder_id).toBe(folder.id);await page.getByRole("region",{name:"Last note action",exact:true}).getByRole("button",{name:"Undo",exact:true}).click();await expect.poll(async()=> (await get()).folder_id).toBeNull();
  await page.getByLabel("More note actions",{exact:true}).click();page.once("dialog",d=>d.accept());await page.getByRole("button",{name:"Move to Trash",exact:true}).click();await expect.poll(async()=> (await get()).deleted_at).not.toBeNull();await page.getByRole("region",{name:"Last note action",exact:true}).getByRole("button",{name:"Undo",exact:true}).click();await expect.poll(async()=> (await get()).deleted_at).toBeNull();expect((await get()).content).toBe("Existing text");
});

test("Ctrl and Shift clicks select ranges without changing the open note",async({page})=>{
  const headers=await login(page);const prefix=`Selection ${Date.now()}`;const records=[];for(const name of ["A","B","C"])records.push(await create(page,headers,`${prefix} ${name}`));await open(page,records[0].id);await page.getByRole("textbox",{name:"Search notes",exact:true}).fill(prefix);await page.getByRole("combobox",{name:"Sort notes",exact:true}).selectOption("title");await expect(page.locator(".notes-card")).toHaveCount(3);
  await page.getByRole("button",{name:new RegExp(`${prefix} A`)}).click({modifiers:["Control"]});await page.getByRole("button",{name:new RegExp(`${prefix} C`)}).click({modifiers:["Shift"]});for(const row of records)await expect(page.getByRole("checkbox",{name:`Select ${row.title}`,exact:true})).toBeChecked();await expect(page.getByRole("textbox",{name:"Note title",exact:true})).toHaveValue(records[0].title);await page.keyboard.press("Escape");await expect(page.getByRole("button",{name:"Move selected notes",exact:true})).toHaveCount(0);
});

test("workspace preferences and last-opened note persist per user",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Remember my workspace");await open(page,note.id);await page.getByRole("combobox",{name:"Sort notes",exact:true}).selectOption("title");await page.getByRole("button",{name:"Change notes view",exact:true}).click();await page.getByLabel("More note actions",{exact:true}).click();await page.getByRole("button",{name:"Editor width: standard",exact:true}).click();await page.getByRole("button",{name:"Collapse folder explorer",exact:true}).click();await page.goto("/pms/notes");await expect(page.getByRole("textbox",{name:"Note title",exact:true})).toHaveValue(note.title);await expect(page.getByRole("combobox",{name:"Sort notes",exact:true})).toHaveValue("title");await expect(page.getByRole("button",{name:"Change notes view",exact:true})).toHaveAttribute("title","View: list");await expect(page.locator(".notes-width-wide")).toBeVisible();await expect(page.getByRole("region",{name:"Private note editor",exact:true}).getByRole("button",{name:"Show folder explorer",exact:true})).toBeVisible();
});

test("slash menu arrow keys choose the active command and shortcut help opens",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Slash keyboard navigation");await open(page,note.id);const editor=page.getByRole("textbox",{name:"Note content",exact:true});await editor.fill("/he");await expect(page.getByRole("menu",{name:"Insert block",exact:true})).toBeVisible();await editor.press("ArrowLeft");await expect(page.getByRole("menu",{name:"Insert block",exact:true})).toHaveCount(0);await editor.fill("/");await expect(page.getByRole("menuitem",{name:"Heading",exact:true})).toHaveAttribute("aria-current","true");await editor.press("ArrowDown");await expect(page.getByRole("menuitem",{name:"Checklist",exact:true})).toHaveAttribute("aria-current","true");await editor.press("Enter");await expect(editor.locator('ul[data-type="taskList"]')).toBeVisible();await page.getByRole("button",{name:"Notes keyboard shortcuts",exact:true}).click();await expect(page.getByRole("dialog")).toContainText("Shift + click");await page.getByRole("button",{name:"Close dialog",exact:true}).click();await editor.press("Control+Shift+f");await expect(page.getByRole("textbox",{name:"Search notes",exact:true})).toBeFocused();
});

test("touch grip reorders blocks on a phone without dragging ordinary text",async({browser})=>{
  const context=await browser.newContext({baseURL:"http://127.0.0.1:5185",hasTouch:true,isMobile:true,viewport:{width:390,height:844}});const page=await context.newPage();const headers=await login(page);const note=await create(page,headers,"Touch drag verification");await open(page,note.id);const editor=page.getByRole("textbox",{name:"Note content",exact:true});await editor.fill("Touch first");await editor.press("Control+End");await editor.press("Enter");await editor.pressSequentially("Touch second");await editor.locator("p").first().tap();
  const handle=page.getByRole("button",{name:"Drag block to reorder",exact:true});await expect(handle).toBeVisible();const source=(await handle.boundingBox())!,target=(await editor.locator("p").nth(1).boundingBox())!;const session=await context.newCDPSession(page);
  await session.send("Input.dispatchTouchEvent",{type:"touchStart",touchPoints:[{x:source.x+source.width/2,y:source.y+source.height/2}]});await session.send("Input.dispatchTouchEvent",{type:"touchMove",touchPoints:[{x:target.x+40,y:target.y+target.height-1}]});await expect(page.locator(".note-block-insertion")).toBeVisible();await session.send("Input.dispatchTouchEvent",{type:"touchEnd",touchPoints:[]});await expect(editor.locator("p")).toHaveText(["Touch second","Touch first"]);await expect.poll(async()=> (await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).content).toMatch(/Touch second.*Touch first/);await context.close();
});

test("stale Undo reports a conflict without changing a newer edit",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Undo conflict verification");await open(page,note.id);await page.getByLabel("More note actions",{exact:true}).click();await page.getByRole("button",{name:"Archive note",exact:true}).click();await expect(page.getByRole("region",{name:"Last note action",exact:true})).toBeVisible();
  const latest=await(await page.request.get(base+`/notes/${note.id}`,{headers})).json();const {version,project_id,task_id,folder_id,tags,pinned,favorite,archived}=latest;expect((await page.request.put(base+`/notes/${note.id}`,{headers,data:{version,title:"Newer protected title",content:"Newer protected content",project_id,task_id,folder_id,tags,pinned,favorite,archived}})).ok()).toBeTruthy();
  await page.getByRole("region",{name:"Last note action",exact:true}).getByRole("button",{name:"Undo",exact:true}).click();await expect(page.getByRole("alert")).toContainText("changed since that action");const after=await(await page.request.get(base+`/notes/${note.id}`,{headers})).json();expect(after.archived).toBe(true);expect(after.content).toBe("Newer protected content");
});

test("history preview renders formatting and restores a new version",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Formatted original",{content:'<!--suite-richtext:v1--><h2>Original heading</h2><p><strong>Original bold</strong></p>'});await open(page,note.id);await page.getByRole("textbox",{name:"Note title",exact:true}).fill("Updated history title");await saved(page,note.id,"Updated history title");await page.getByLabel("More note actions",{exact:true}).click();await page.getByRole("button",{name:"Version history",exact:true}).click();await page.getByRole("button",{name:/Version 1 · Formatted original/}).click();await expect(page.locator(".notes-history-preview h2")).toHaveText("Original heading");await expect(page.locator(".notes-history-preview strong")).toHaveText("Original bold");await page.getByRole("button",{name:"Restore as new version",exact:true}).click();await saved(page,note.id,"Formatted original");expect((await(await page.request.get(base+`/notes/${note.id}`,{headers})).json()).version).toBeGreaterThan(2);
});

test("revoking the last reader immediately returns the note badge to Private",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Privacy badge verification");await open(page,note.id);await page.getByRole("button",{name:"Share",exact:true}).click();await page.getByRole("textbox",{name:"Share with colleague email",exact:true}).fill("notes-reader@example.com");await page.getByRole("button",{name:"Invite to read",exact:true}).click();await expect(page.getByRole("button",{name:"Revoke access",exact:true})).toBeVisible();await expect(page.locator(".notes-privacy-badge")).toHaveText("Shared");await page.getByRole("button",{name:"Revoke access",exact:true}).click();await expect(page.locator(".notes-privacy-badge")).toHaveText("Private");
});

test("returning to an empty folder preserves its scope instead of reopening an unrelated note",async({page})=>{
  const headers=await login(page);const note=await create(page,headers,"Unrelated last note");const folder=await(await page.request.post(base+"/note-folders",{headers,data:{name:`Empty remembered folder ${Date.now()}`}})).json();await open(page,note.id);await page.getByRole("treeitem",{name:new RegExp(folder.name)}).click();await expect(page.getByRole("region",{name:"Note list",exact:true}).getByRole("heading",{name:folder.name,exact:true})).toBeVisible();await page.goto("/pms/notes");await expect(page.getByRole("region",{name:"Note list",exact:true}).getByRole("heading",{name:folder.name,exact:true})).toBeVisible();await expect(page.locator(".notes-document-empty")).toBeVisible();
});
