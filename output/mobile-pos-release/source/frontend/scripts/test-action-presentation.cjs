const {chromium,expect}=require('playwright/test');
(async()=>{
 const browser=await chromium.launch();
 try { for(const width of [1440,390,320]) {
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/action-presentation-qa',route=>route.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>(type)=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/fixtures/action-presentation-qa.tsx');</script>`}));
  await page.goto((process.env.QA_BASE_URL||'http://127.0.0.1:5188')+'/action-presentation-qa');
  const tasks=page.locator('[data-action-presentation=task],.suite-action[data-action=task]');
  await expect(tasks).toHaveCount(6);
  for(const task of await tasks.all()) { await expect(task.locator('svg')).toHaveCount(1); expect((await task.textContent()).trim().startsWith('+')).toBe(false); expect(await task.evaluate(e=>getComputedStyle(e).color)).toBe('rgb(255, 255, 255)'); expect(await task.evaluate(e=>getComputedStyle(e).backgroundImage)).toContain('linear-gradient'); }
  await expect(page.getByRole('button',{name:'Export',exact:true})).toHaveAttribute('data-action-tone','emerald');
  await expect(page.getByRole('button',{name:'Trash',exact:true})).toHaveAttribute('data-action-tone','red');
  await expect(page.getByRole('button',{name:'Import',exact:true})).toHaveAttribute('data-action-tone','purple');
  await expect(page.locator('[data-count-badge]')).toHaveCount(2);
  await expect(page.locator('[data-count-badge]').first()).toHaveText('0');
  await page.getByRole('button',{name:'More actions',exact:true}).click();
  await expect(page.getByRole('menuitem',{name:'Copy',exact:true})).toBeVisible();
  await page.keyboard.press('Escape');await expect(page.getByRole('menu')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.evaluate(()=>document.documentElement.classList.add('dark'));
  expect(await tasks.first().evaluate(e=>getComputedStyle(e).color)).toBe('rgb(255, 255, 255)');
  expect(errors).toEqual([]);console.log(`PASS ${width}px: composed/link/plain task buttons, single icons, semantic colors, zero counts, menu keyboard dismissal, dark theme, no overflow`);await page.close();
 }} finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
