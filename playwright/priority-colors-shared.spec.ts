import {test,expect} from "../frontend/node_modules/playwright/test";
for(const module of ["crm","pms","srm","hrms"])test(`${module} uses the shared priority palette`,async({page},testInfo)=>{
 await page.route('**/api/**',route=>route.fulfill({json:{items:[],preferences:{},views:[]}}));
 await page.route(`**/${module}/__priority-colors`,route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/priority-colors-qa.tsx"></script></body></html>`}));
 await page.goto(`/${module}/__priority-colors`);
 const native=page.getByRole('region',{name:'Native records'}).locator('tr[data-priority-row]');
 await expect(native).toHaveCount(4);
 const expected=['rgb(255, 240, 242)','rgb(255, 244, 233)','rgb(255, 250, 231)','rgb(237, 249, 242)'];
 const colors=await native.evaluateAll(rows=>rows.map(row=>getComputedStyle(row.querySelector('td')!).backgroundColor));expect(colors).toEqual(expected);
 const adapted=page.getByRole('region',{name:'Adapted records'}).locator('[role="row"][data-priority-row="true"]');
 await expect(adapted).toHaveCount(6);
 expect(await adapted.evaluateAll(rows=>rows.slice(0,4).map(row=>getComputedStyle(row).backgroundColor))).toEqual(expected);
 const cards=page.getByRole('region',{name:'Record cards'}).locator('article');
 expect(await cards.evaluateAll(rows=>rows.map(row=>getComputedStyle(row).backgroundColor))).toEqual(expected);
 await page.getByLabel('Priority 3',{exact:true}).selectOption('Urgent');await expect(native.last()).toHaveAttribute('data-priority','urgent');
 await page.locator('html').evaluate(node=>node.classList.add('dark'));
 const darkColors=await cards.evaluateAll(rows=>rows.map(row=>getComputedStyle(row).backgroundColor));expect(new Set(darkColors).size).toBe(4);
 if(module==='crm')await page.screenshot({path:testInfo.outputPath('priority-colors-dark.png'),fullPage:true});
});
