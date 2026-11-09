const {build}=require('esbuild'),{chromium,expect:baseExpect}=require('playwright/test'),path=require('path'),assert=require('node:assert/strict');
const expect=baseExpect.configure({timeout:10000});
(async()=>{
 const root=process.env.NOTE_TEST_ROOT||path.resolve(__dirname,'..');
 const source=`import React from 'react';import {createRoot} from 'react-dom/client';import {BrowserRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import NotesPage from './src/apps/project-management/pages/NotesPage';import {useAuthStore} from './src/store/authStore';import './src/index.css';useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,email:'notes@test.invalid',role:'super_admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><NotesPage/></BrowserRouter></QueryClientProvider>);`;
 const output=await build({stdin:{contents:source,resolveDir:root,loader:'tsx'},bundle:true,write:false,outfile:'notes-optimistic.js',format:'iife',platform:'browser',alias:{'@':path.join(root,'src')},banner:{js:'globalThis.__noteTestGlob=()=>({});'},define:{'import.meta.env':'{}','import.meta.glob':'globalThis.__noteTestGlob'},plugins:[{name:'worker-url',setup(b){b.onResolve({filter:/\?url$/},a=>({path:a.path,namespace:'worker-url'}));b.onLoad({filter:/.*/,namespace:'worker-url'},()=>({contents:'export default "/test-worker.js"'}));}}],loader:{'.png':'dataurl','.svg':'dataurl','.woff2':'dataurl'}});
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage({viewport:{width:1480,height:1000}}),errors=[];page.setDefaultTimeout(12000);page.on('pageerror',e=>{errors.push(e.message);console.log('JS ERROR',e.stack)});
  let note={id:7,title:'Original title',content:'Original content',preview:'Original content',tags:[],pinned:false,favorite:false,archived:false,project_id:null,task_id:null,folder_id:null,project_name:'',task_title:null,visibility:'private',version:1,created_at:new Date().toISOString(),updated_at:new Date().toISOString(),deleted_at:null,can_edit:true};
  let pending=null,writes=[];
  await page.route('http://notes.test/**',async route=>{const r=route.request(),url=new URL(r.url());if(!url.pathname.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:'<div id="root"></div>'});
   if(['PUT','POST'].includes(r.method())&&/\/notes(?:\/[78])?$/.test(url.pathname)){writes.push({method:r.method(),body:r.postDataJSON(),path:url.pathname});pending=route;return;}
   if(url.pathname.endsWith('/attachments'))return route.fulfill({json:{items:[],removed_items:[],max_file_bytes:1000000,max_files:10,max_note_bytes:10000000}});
   if(url.pathname.endsWith('/notes/7'))return route.fulfill({json:note});
   if(url.pathname.endsWith('/notes'))return route.fulfill({json:[note]});
   if(/\/(projects|note-folders|backlinks|attachments)$/.test(url.pathname))return route.fulfill({json:[]});
   return route.fulfill({json:[]});
  });
  await page.goto('http://notes.test/pms/notes?note=7');for(const f of output.outputFiles)if(f.path.endsWith('.css'))await page.addStyleTag({content:f.text});for(const f of output.outputFiles)if(f.path.endsWith('.js'))await page.addScriptTag({content:f.text});
  const title=page.getByLabel('Note title',{exact:true}),card=page.locator('.notes-card').first();await expect(title).toHaveValue('Original title');
  await title.fill('Instant local title');await page.getByRole('textbox',{name:'Note content',exact:true}).fill('Instant preview text');await page.getByRole('button',{name:'Save note',exact:true}).click();
  await expect(card).toContainText('Instant local title');await expect(card).toContainText('Instant preview text');await expect(card.getByRole('progressbar',{name:'Syncing note to server'})).toBeVisible();assert.equal(writes.length,1);assert.equal(note.title,'Original title');await page.screenshot({path:path.join(root,'..','.local','shared-notes-release','optimistic-save.png')});
  await title.fill('Newer typing during sync');await expect(title).toHaveValue('Newer typing during sync');
  note={...note,...writes[0].body,preview:'Instant preview text',version:2};await pending.fulfill({json:note});pending=null;await expect(card.getByRole('progressbar')).toHaveCount(0);await expect(title).toHaveValue('Newer typing during sync');
  // The next autosave must use the acknowledged revision and latest draft.
  await expect.poll(()=>writes.length).toBe(2);assert.equal(writes[1].body.title,'Newer typing during sync');assert.equal(writes[1].body.version,2);
  await pending.fulfill({status:503,json:{detail:'Temporarily unavailable'}});pending=null;await expect(card.getByRole('img',{name:'Note not synced — draft kept'})).toBeVisible();await expect(card).toContainText('Newer typing during sync');await expect(title).toHaveValue('Newer typing during sync');
  await page.getByRole('button',{name:'Retry save',exact:true}).click();await expect.poll(()=>writes.length).toBe(3);assert.equal(writes[2].body.version,2);note={...note,...writes[2].body,version:3};await pending.fulfill({json:note});pending=null;await expect(card.getByRole('img',{name:'Note not synced — draft kept'})).toHaveCount(0);await expect(title).toHaveValue('Newer typing during sync');
  // A brand-new note appears before POST completes, without any negative-ID API requests.
  await page.getByRole('button',{name:'New Note',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Create private note'})).toHaveCount(0);
  await title.fill('Instant new note');await title.evaluate(el=>el.dataset.editorIdentity='unchanged');
  await expect.poll(()=>writes.length).toBe(4);assert.equal(writes[3].method,'POST');
  await expect(title).toBeFocused();await expect(title).toHaveAttribute('data-editor-identity','unchanged');
  await expect(page.locator('.notes-card').filter({hasText:'Instant new note'})).toBeVisible();
  note={...note,...writes[3].body,id:8,version:1};await pending.fulfill({json:note});pending=null;
  await expect(page).toHaveURL(/note=8/);await expect(title).toBeFocused();await expect(title).toHaveAttribute('data-editor-identity','unchanged');
  await title.press('End');await title.pressSequentially(' keeps editing');await expect.poll(()=>writes.length).toBe(5);
  assert.equal(writes[4].method,'PUT');assert.equal(writes[4].path,'/api/v1/project-management/notes/8');
  note={...note,...writes[4].body,version:2};await pending.fulfill({json:note});pending=null;
  await expect(title).toHaveValue('Instant new note keeps editing');await expect(title).toBeFocused();
  assert.equal(await page.locator('.notes-card').filter({hasText:'Instant new note'}).count(),1);assert.deepEqual(errors,[]);
  console.log('PASS: immediate item update, tiny sync indicator, newer typing preserved, failed-save recovery/retry, acknowledged versions, and optimistic create without duplicates.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
