import {test,expect,type Page} from '../frontend/node_modules/playwright/test';

async function setup(page:Page,badPath=''){
  let broken=!!badPath;
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const suffix=path.endsWith('/project-options')?'project':path.endsWith('/staff-options')?'staff':path.endsWith('/catalog/items')?'service':'';
    if(suffix){
      if(suffix===badPath&&broken)return route.fulfill({json:[]});
      return route.fulfill({json:{items:[{id:1,name:`First ${suffix}`,kind:'service'},{id:2,name:`Second ${suffix}`,kind:'service'}],has_more:false,pages:1}});
    }
    return route.fulfill({json:{values:{},modules:{}}});
  });
  await page.route('**/srm-picker-qa',route=>route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/srm-picker-recovery.tsx");</script>'}));
  await page.goto('/srm-picker-qa');
  return ()=>{broken=false;};
}

for(const width of [390,1440])test(`industry picker labels follow reset and changed IDs at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:900});
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await setup(page);
  for(const kind of ['Project','Staff','Service']){
    const section=page.getByRole('region',{name:`${kind} test`});
    await section.getByRole('combobox').click();
    await section.getByRole('option',{name:`First ${kind.toLowerCase()}`,exact:true}).click();
    await expect(section.getByRole('combobox')).toHaveValue(`First ${kind.toLowerCase()}`);
  }
  await page.getByRole('button',{name:'Replace selections'}).click();
  for(const kind of ['Project','Staff','Service'])await expect(page.getByRole('region',{name:`${kind} test`}).getByRole('combobox')).toHaveValue(`Second ${kind.toLowerCase()}`);
  await page.getByRole('button',{name:'Reset selections'}).click();
  for(const kind of ['Project','Staff','Service'])await expect(page.getByRole('region',{name:`${kind} test`}).getByRole('combobox')).toHaveValue('');
  expect(errors).toEqual([]);
});

for(const kind of ['project','staff','service'])test(`${kind} picker recovers from malformed data without crashing`,async({page})=>{
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  const recover=await setup(page,kind);
  const section=page.getByRole('region',{name:`${kind[0].toUpperCase()+kind.slice(1)} test`});
  await expect(section.getByRole('alert')).toBeVisible();
  recover();await section.getByRole('button',{name:'Retry',exact:true}).click();
  await section.getByRole('combobox').click();
  await expect(section.getByRole('option',{name:`First ${kind}`,exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});
