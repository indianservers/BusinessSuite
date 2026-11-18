const fs=require('node:fs'),path=require('node:path');
const {chromium,expect}=require('playwright/test');
(async()=>{
  process.chdir(path.resolve(__dirname,'..'));
  const fixture=path.resolve(`scripts/.compact-booking-${process.pid}.tsx`);
  fs.writeFileSync(fixture,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import '@/index.css';import '@/apps/srm/pages/srm-pos-mobile.css';import Scheduling from '@/apps/srm/industry/POSServiceScheduling';import Settings from '@/apps/srm/components/POSBookingSettings';import{useAuthStore}from'@/store/authStore';useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,role:'super_admin',is_superuser:true}});function App(){const[mode,M]=React.useState('dialog'),[booking,B]=React.useState(),[required,R]=React.useState(false);return <><Settings value={mode} onChange={M}/><div style={{maxWidth:420}}><Scheduling presentation={mode} compactSummary="Choose employee & time" productId={9} lineKey="test" value={booking} onChange={B} onRequirement={R}/></div><output id="booking">{JSON.stringify(booking)}</output><output id="required">{String(required)}</output></>};createRoot(document.getElementById('root')).render(<MemoryRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><App/></QueryClientProvider></MemoryRouter>);`);
  let browser,server;
  try{
    const{createServer}=await import('vite');const{default:react}=await import('@vitejs/plugin-react');
    server=await createServer({configFile:false,plugins:[react()],resolve:{alias:{'@':path.resolve('src')}},cacheDir:path.resolve('node_modules/.vite-pos-compact'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null},optimizeDeps:{entries:[fixture]}});await server.listen();browser=await chromium.launch();
    for(const [width,height]of [[320,480],[320,568],[360,480],[360,640],[390,844],[768,600],[844,390],[1280,720],[1920,1080]]){
      const page=await browser.newPage({viewport:{width,height}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
      const slotsPerPage=width<640&&height<=520?2:4,zone=width===390?'Asia/Kolkata':'UTC',offset=zone==='UTC'?'Z':'+05:30';
      let failed=false,conflict=false;
      await page.route('**/api/v1/**',async route=>{
        const url=new URL(route.request().url());
        if(url.pathname.endsWith('/options/availability')){
          await new Promise(resolve=>setTimeout(resolve,450));
          if(failed)return route.fulfill({status:503,json:{detail:'Try again'}});
          const day=url.searchParams.get('day');return route.fulfill({json:{timezone:zone,selection_available:url.searchParams.has('starts_at')?!conflict:null,slots:Array.from({length:24},(_,i)=>({starts_at:`${day}T${String(9+Math.floor(i/2)).padStart(2,'0')}:${i%2?'30':'00'}:00${offset}`,label:`${String(9+Math.floor(i/2)).padStart(2,'0')}:${i%2?'30':'00'}`})),resources:[]}});
        }
        return route.fulfill({json:{policy:{id:4,revision:1,active:true,booking_required:width!==320,default_duration_minutes:30,min_duration_minutes:5,max_duration_minutes:120,allow_duration_override:true,required_resource_types:['room']},specialists:[{eligibility_id:1,eligibility_revision:1,provider_resource_id:11,employee_id:21,employee_name:'Alex Staff',provider_name:'Consultations',timezone:zone}],resources:Array.from({length:20},(_,i)=>({id:30+i,name:i===0?'Consultation room with a deliberately very long descriptive resource name that must not grow the booking form':`Room ${i+1}`,resource_type:'room'})),has_more:false}});
      });
      await page.route('**/compact-booking-qa',route=>route.fulfill({contentType:'text/html',body:`<meta charset="utf-8"><div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}')</script>`}));
      await page.goto(server.resolvedUrls.local[0]+'compact-booking-qa');await page.locator('.pos-booking-trigger').click();
      async function fits(node){const m=await node.evaluate(el=>({scroll:el.scrollHeight,height:el.clientHeight,top:el.getBoundingClientRect().top,bottom:el.getBoundingClientRect().bottom,nested:[...el.querySelectorAll('*')].filter(n=>['auto','scroll'].includes(getComputedStyle(n).overflowY)&&n.scrollHeight>n.clientHeight+1).length}));if(m.scroll>m.height+1)console.log('overflow',width,height,await node.locator('.pos-compact-tabs button[aria-pressed=true]').textContent(),m);expect(m.scroll).toBeLessThanOrEqual(m.height+1);expect(m.top).toBeGreaterThanOrEqual(0);expect(m.bottom).toBeLessThanOrEqual(height);expect(m.nested).toBe(0);}
      const dialog=page.getByRole('dialog',{name:'Service booking'}),apply=dialog.getByRole('button',{name:'Use these booking details',exact:true});
      const optional=dialog.getByRole('checkbox',{name:'Schedule this service',exact:true});if(width===320)await optional.check();
      await expect(apply).toBeEnabled({timeout:30000});
      await expect(page.locator('#required')).toHaveText('true');
      const minutes=dialog.getByLabel('Booking duration test',{exact:true});await minutes.fill('500');await expect(apply).toBeDisabled();await expect(dialog.getByRole('alert')).toContainText('Use 5–120 minutes');await fits(dialog);await minutes.fill('30');await expect(apply).toBeEnabled();
      await expect(dialog.locator('.pos-compact-time-buttons button')).toHaveCount(slotsPerPage);
      await dialog.locator('.pos-compact-time-buttons button').nth(1).click();
      await expect(dialog.locator('.pos-compact-availability')).toHaveAttribute('aria-busy','true');
      await expect(dialog.locator('.pos-compact-time-buttons button')).toHaveCount(slotsPerPage);await expect(apply).toBeDisabled();await expect(apply).toBeEnabled();
      await dialog.getByRole('button',{name:'Next available times',exact:true}).click();await expect(dialog.locator('.pos-compact-time-buttons button')).toHaveCount(slotsPerPage);
      await expect(dialog.locator('.pos-compact-times nav')).toContainText(`${slotsPerPage+1}–${slotsPerPage*2} of 24`);
      const metrics=await dialog.evaluate(node=>({scroll:node.scrollHeight,height:node.clientHeight,top:node.getBoundingClientRect().top,bottom:node.getBoundingClientRect().bottom}));expect(metrics.scroll).toBeLessThanOrEqual(metrics.height+1);expect(metrics.top).toBeGreaterThanOrEqual(0);expect(metrics.bottom).toBeLessThanOrEqual(height);
      await page.screenshot({path:`../output/pos-service-booking-compact-${width}.png`});
      conflict=true;await dialog.locator('.pos-compact-time-buttons button').first().click();await expect(dialog.getByRole('status')).toContainText('unavailable');await expect(apply).toBeDisabled();
      conflict=false;failed=true;await dialog.locator('.pos-compact-time-buttons button').nth(1).click();await expect(dialog.getByRole('alert')).toContainText('Could not verify times');await expect(dialog.locator('.pos-compact-time-buttons button')).toHaveCount(slotsPerPage);await fits(dialog);await expect(apply).toBeDisabled();
      failed=false;await dialog.getByRole('button',{name:'Refresh',exact:true}).click();await expect(apply).toBeEnabled();
      conflict=true;await apply.click();await expect(dialog.getByRole('alert')).toContainText('unavailable');const errorMetrics=await dialog.evaluate(node=>({scroll:node.scrollHeight,height:node.clientHeight,bottom:node.getBoundingClientRect().bottom}));expect(errorMetrics.scroll).toBeLessThanOrEqual(errorMetrics.height+1);expect(errorMetrics.bottom).toBeLessThanOrEqual(height);conflict=false;await dialog.getByRole('button',{name:'Refresh',exact:true}).click();await expect(apply).toBeEnabled();await expect(dialog.getByRole('alert')).toHaveCount(0);
      await dialog.getByRole('button',{name:'Resources (1)',exact:true}).click();await expect(dialog.locator('.pos-compact-resources input')).toHaveCount(6);await fits(dialog);await dialog.getByRole('button',{name:'Find staff',exact:true}).click();await fits(dialog);await dialog.getByRole('button',{name:'Resources (1)',exact:true}).click();await dialog.getByRole('button',{name:'Next resources'}).click();await expect(dialog.getByRole('checkbox',{name:'Room 7',exact:true})).toBeVisible();
      await dialog.getByRole('checkbox',{name:'Room 7',exact:true}).check();await expect(apply).toBeEnabled();await apply.click();await expect(dialog).toBeHidden();
      expect(JSON.parse(await page.locator('#booking').textContent()).additional_resource_ids).toEqual([30,36]);
      await page.getByLabel('Service booking layout').selectOption('cart');await expect(page.getByRole('dialog')).toHaveCount(0);await page.getByRole('button',{name:'Edit employee & time',exact:true}).click();await expect(page.getByLabel('Specialist test',{exact:true})).toBeVisible();
      await expect(page.locator('.pos-booking-trigger')).toHaveCount(0);await page.getByRole('button',{name:'Time',exact:true}).click();const times=page.getByLabel('Available times test',{exact:true});await expect(times.locator('option')).toHaveCount(25);await times.selectOption({index:2});await expect(page.getByRole('button',{name:'Use these booking details',exact:true})).toBeDisabled();await expect(times.locator('option')).toHaveCount(25);await expect(page.getByRole('button',{name:'Use these booking details',exact:true})).toBeEnabled();failed=true;await times.selectOption({index:4});await expect(page.getByRole('alert')).toContainText('Could not verify times');await expect(times.locator('option')).toHaveCount(25);failed=false;await page.getByRole('button',{name:'Refresh',exact:true}).click();await expect(page.getByRole('button',{name:'Use these booking details',exact:true})).toBeEnabled();expect(errors).toEqual([]);await page.close();
    }
    console.log('PASS compact POS booking: nine mobile/desktop viewports, all tabs without vertical overflow, stable slots during refresh/failure, UTC/India timezones, duration validation, conflict retry, required/optional scheduling, cart/dialog modes');
  }finally{await browser?.close();await server?.close();fs.unlinkSync(fixture);}
})().catch(error=>{console.error(error);process.exitCode=1;});
