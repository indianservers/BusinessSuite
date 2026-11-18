const fs=require('node:fs'),path=require('node:path'),{chromium,expect:baseExpect}=require('playwright/test');
const expect=baseExpect.configure({timeout:30000});
(async()=>{
 const fixture=path.join(__dirname,'.audit-utility-overlap.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Team from'@/components/app/WorkspaceEnhancements';import Bot from'@/components/ai-agents/ActionBot';import Back from'@/components/app/BackToTop';import Dock from'@/components/layout/MobileModuleDock';import{useAuthStore}from'@/store/authStore';import'@/index.css';import'@/components/layout/mobile-workspaces.css';useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/hrms/assets']}><div className="product-shell flex h-screen"><div className="flex min-w-0 flex-1 flex-col overflow-hidden"><header style={{height:64,flexShrink:0}}>Application bar</header><main id="suite-main" className="kf-main suite-page-surface min-w-0 flex-1 overflow-auto animate-fade-in"><Team/>{Array.from({length:30},(_,i)=><article key={i} style={{height:90,border:'1px solid gray'}}>Asset row {i}</article>)}</main><Back/></div></div><Bot/><Dock/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root:path.resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{const page=await browser.newPage();const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});await page.route('**/api/v1/**',r=>r.fulfill({json:[]}));
 await page.route('**/utility-overlap-qa',r=>r.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-utility-overlap.tsx');</script>`}));
 await page.goto(server.resolvedUrls.local[0]+'utility-overlap-qa');await expect(page.getByRole('button',{name:'Team workspace',exact:true})).toBeVisible();
 for(const width of [1280,1024,768]){
 await page.setViewportSize({width,height:495});await page.locator('#suite-main').evaluate(el=>el.scrollTop=500);await expect(page.getByRole('button',{name:'Back to top',exact:true})).toBeVisible();
 const content=await page.locator('#suite-main').boundingBox(),boxes=[];for(const name of ['Team workspace','Back to top','Open action bot']){const box=await page.getByRole('button',{name,exact:true}).boundingBox();expect(box.x).toBeGreaterThanOrEqual(content.x+content.width);expect(box.x+box.width).toBeLessThanOrEqual(width);boxes.push(box);}
 for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){const a=boxes[i],b=boxes[j];expect(a.x+a.width<=b.x||b.x+b.width<=a.x||a.y+a.height<=b.y||b.y+b.height<=a.y).toBe(true);}
 }
 await page.getByRole('button',{name:'Team workspace',exact:true}).click();await expect(page.getByRole('dialog',{name:'Team workspace',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Open action bot',exact:true})).toBeHidden();await page.getByRole('button',{name:'Close team workspace',exact:true}).click();await expect(page.getByRole('button',{name:'Open action bot',exact:true})).toBeVisible();expect(errors).toEqual([]);
 for(const width of [320,390,480,600,767]){
 await page.setViewportSize({width,height:672});
 const dock=page.getByRole('navigation',{name:'HRMS mobile navigation'});
 await expect(dock).toBeVisible();
 await page.locator('#suite-main').evaluate(el=>el.scrollTop=500);
 await expect(page.locator('.workspace-back-to-top')).toBeHidden();
 const launcher=page.getByRole('button',{name:'Open action bot',exact:true});
 await expect(launcher).toBeVisible();
 const dockBox=await dock.boundingBox(),botBox=await launcher.boundingBox();
 expect(botBox.y+botBox.height).toBeLessThanOrEqual(dockBox.y-8);
 const mainBox=await page.locator('#suite-main').boundingBox(),toolsBox=await page.getByRole('button',{name:'Workspace tools',exact:true}).boundingBox();
 expect(mainBox.y+mainBox.height).toBeLessThanOrEqual(Math.min(botBox.y,toolsBox.y)-8);
 await page.getByRole('button',{name:'Workspace tools',exact:true}).click();
 const tools=page.getByRole('dialog',{name:'Workspace tools',exact:true});
 await expect(tools).toBeVisible();await expect(launcher).toBeHidden();
 await page.keyboard.press('Escape');await expect(tools).toBeHidden();await expect(launcher).toBeVisible();
 await launcher.click();const panel=page.getByRole('dialog',{name:'Action bot',exact:true});await expect(panel).toBeVisible();
 const panelBox=await panel.boundingBox(),openedBot=await page.getByRole('button',{name:'Minimize action bot',exact:true}).boundingBox();
 expect(panelBox.y).toBeGreaterThanOrEqual(0);expect(panelBox.y+panelBox.height).toBeLessThanOrEqual(openedBot.y-8);
 expect(panelBox.x).toBeGreaterThanOrEqual(0);expect(panelBox.x+panelBox.width).toBeLessThanOrEqual(width);
 if(width<=600){await page.getByRole('button',{name:'Expand bot workspace'}).click();await expect(panel).toHaveClass(/action-bot-expanded/);const full=await panel.boundingBox();expect(full.height).toBeGreaterThan(640);await page.getByRole('button',{name:'Collapse bot workspace'}).click();}
 await page.getByRole('button',{name:'Close action bot',exact:true}).click();await expect(panel).toBeHidden();
 await page.evaluate(()=>{const marker=document.createElement('div');marker.className='srm-pos';marker.id='qa-pos-marker';document.body.append(marker)});
 const posBot=await launcher.boundingBox(),posTools=await page.getByRole('button',{name:'Workspace tools',exact:true}).boundingBox();
 expect(posBot.x+posBot.width).toBeLessThanOrEqual(posTools.x-8);
 expect(Math.abs(posBot.y-posTools.y)).toBeLessThanOrEqual(4);
 await page.evaluate(()=>document.getElementById('qa-pos-marker').remove());
 await page.evaluate(()=>document.body.classList.add('mobile-keyboard-open'));
 await expect(dock).toBeHidden();await expect(launcher).toBeHidden();
 const keyboardMain=await page.locator('#suite-main').boundingBox();expect(keyboardMain.height).toBeGreaterThan(mainBox.height+100);
 await page.evaluate(()=>document.body.classList.remove('mobile-keyboard-open'));
 await expect(dock).toBeVisible();await expect(launcher).toBeVisible();
 if(width===390){await page.locator('#suite-main').evaluate(el=>Promise.all(el.getAnimations().map(animation=>animation.finished)));fs.mkdirSync(path.resolve(__dirname,'../outputs'),{recursive:true});await page.screenshot({path:path.resolve(__dirname,'../outputs/erp-audit-mobile-utilities.png')});}
 }
 expect(errors).toEqual([]);
 console.log('PASS desktop utilities: reserved content strip, controls do not overlap rows or each other at 1280/1024/768; team dialog and assistant dismissal preserved; mobile dock/assistant clearance and workspace-tool dismissal at 320/390/480/600/767');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
