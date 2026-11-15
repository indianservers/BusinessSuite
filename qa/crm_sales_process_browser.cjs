const {chromium}=require('../frontend/node_modules/playwright');
const fs=require('node:fs');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/crm-sales-qa.html',{waitUntil:'domcontentloaded'});
 await page.getByRole('heading',{name:'Consultations & demos',exact:true}).waitFor({timeout:60000});
 await page.getByText('40',{exact:true}).waitFor();
 await page.locator('summary').filter({hasText:'Sales process & automation'}).click();
 await page.getByRole('button',{name:'Enable sales process & automation',exact:true}).click();
 await page.getByText('Sales process & automation · Enabled',{exact:true}).waitFor();
 await page.getByText('Consultations, demo outcomes & nurture permission',{exact:true}).click();
 await page.getByRole('button',{name:'Confirm',exact:true}).click();
 await page.getByRole('button',{name:'Attended',exact:true}).click();
 await page.getByText(/Jan 1, 2026.*Attended/).waitFor().catch(async()=>{if(!(await page.locator('article').innerText()).includes('Attended'))throw Error('Attendance did not persist');});
 await page.getByLabel('Permission to receive nurture follow-ups').check();
 await page.getByLabel('Permission evidence / withdrawal reason').fill('Permission recorded in a call');
 await page.getByRole('button',{name:'Record nurture permission',exact:true}).click();
 await page.getByText('Nurture permission saved',{exact:true}).waitFor();
 fs.mkdirSync('output/crm-sales-process',{recursive:true});
 await page.screenshot({path:'output/crm-sales-process/fixture-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'output/crm-sales-process/fixture-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
 await page.getByRole('button',{name:'Inspect fixture requests'}).click();
 console.log(JSON.stringify({errors,overflow,requests:JSON.parse(await page.locator('output').innerText())}));
 if(errors.length||overflow)throw Error('UI verification failed');
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});

