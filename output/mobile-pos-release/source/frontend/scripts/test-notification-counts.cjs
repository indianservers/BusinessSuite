const { buildSync } = require('esbuild');
const { chromium, expect } = require('playwright/test');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const contents = `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider,useQuery} from '@tanstack/react-query';
import NotificationsPage from './src/apps/hrms/pages/notifications/NotificationsPage';
import SuiteNotificationBell from './src/components/suite/SuiteNotificationBell';
import {refreshNotifications} from './src/lib/notification-cache';
import {api} from './src/services/api';
import {useAuthStore} from './src/store/authStore';
const client=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity},mutations:{retry:false}}});
useAuthStore.setState({user:{id:1,role:'admin',is_superuser:true,access:{companyId:1,grants:{},modules:[],managed:false}},isAuthenticated:true});
const items=[1,2].map(id=>({id,title:'Notification '+id,message:'Read this update',module:'hrms',action_url:'/hrms/dashboard',is_read:false,priority:'normal',created_at:'2026-11-04T00:00:00Z'}));
window.failRead=false;
api.defaults.adapter=async config=>{
 const url=config.url;
 if(config.method==='put'){
  if(window.failRead)throw new Error('Read failed');
  if(url.endsWith('/mark-all-read'))items.forEach(n=>n.is_read=true);
  else items.find(n=>url.endsWith('/'+n.id+'/read')).is_read=true;
 }
 const unread=items.filter(n=>!n.is_read).length;
 let data=url.endsWith('/summary')?{groups:[{module:'hrms',action_url:'/hrms/dashboard',count:unread}]}:url.endsWith('/unread-count')?{unread}:{items:items.filter(n=>!config.params?.unread_only||!n.is_read).map(n=>({...n})),total:items.length,pages:1};
 return {data,status:200,statusText:'OK',headers:{},config};
};
function OtherViews(){
 const profile=useQuery({queryKey:['profile-notifications',1,1],queryFn:()=>api.get('/notifications/').then(r=>r.data)});
 const legacy=useQuery({queryKey:['notifications-unread-count',1],queryFn:()=>api.get('/notifications/unread-count').then(r=>r.data)});
 return <><output data-testid="profile-unread">{profile.data?.items.filter(n=>!n.is_read).length}</output><output data-testid="legacy-count">{legacy.data?.unread}</output><button onClick={async()=>{await api.put('/notifications/1/read');await refreshNotifications(client)}}>Read from PMS</button></>;
}
createRoot(document.getElementById('root')).render(<QueryClientProvider client={client}><MemoryRouter><SuiteNotificationBell/><OtherViews/><NotificationsPage/></MemoryRouter></QueryClientProvider>);
`;
(async()=>{
 const assets=buildSync({outfile:'notification-test.js',stdin:{contents,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'iife',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}}).outputFiles;
 const browser=await chromium.launch({headless:true});
 try {
  async function setup(){
   const page=await browser.newPage();
   await page.route('http://notification.test/',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
   await page.goto('http://notification.test/');
   const css=assets.find(f=>f.path.endsWith('.css'));if(css)await page.addStyleTag({content:css.text});
   await page.addScriptTag({content:assets.find(f=>f.path.endsWith('.js')).text});
   await counts(page,2);return page;
  }
  async function counts(page,count){
   await expect(page.getByRole('button',{name:count?'Notifications, '+count+' unread':'Notifications',exact:true})).toBeVisible();
   await expect(page.getByTestId('legacy-count')).toHaveText(String(count));
   await expect(page.getByTestId('profile-unread')).toHaveText(String(count));
  }
  let page=await setup();
  await page.getByRole('button',{name:'Read from PMS',exact:true}).click();await counts(page,1);
  await page.getByRole('button',{name:'Mark all read',exact:true}).click();await counts(page,0);await page.close();
  page=await setup();
  await page.getByRole('button',{name:'Mark read',exact:true}).first().click();await counts(page,1);
  await page.getByRole('link',{name:'Open',exact:true}).nth(1).click();await counts(page,0);await page.close();
  page=await setup();
  await page.getByRole('button',{name:'Notifications, 2 unread',exact:true}).click();
  await page.getByRole('button').filter({hasText:'Notification 1'}).click();await counts(page,1);await page.close();
  page=await setup();await page.evaluate(()=>window.failRead=true);
  await page.getByRole('button',{name:'Mark read',exact:true}).first().click();await counts(page,2);await page.close();
  console.log('Notification counts passed: PMS read, HRMS read/open/all-read, bell read, cross-view refresh, failed-read count preservation.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
