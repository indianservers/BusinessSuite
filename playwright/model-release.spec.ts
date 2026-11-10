import {test,expect} from '../frontend/node_modules/playwright/test';

test('platform model release requires evaluation and offers verified rollback',async({page})=>{
 await page.goto('/model-release-qa.html');
 await expect(page.getByRole('heading',{name:'NLP training',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Activate model #220'})).toBeDisabled();
 await page.getByRole('button',{name:'Evaluate candidate #220'}).click();
 await expect(page.getByRole('button',{name:'Activate model #220'})).toBeEnabled();
 await page.getByRole('button',{name:'Activate model #220'}).click();
 await expect(page.getByText('Active model: run #220.',{exact:false})).toBeVisible();
 await page.getByRole('button',{name:'Roll back to verified model #218'}).click();
 await expect(page.getByText('Active model: run #218.',{exact:false})).toBeVisible();
 const paths=await page.evaluate(()=>(window as any).__releaseRequests);
 expect(paths.some((p:string)=>/bundle\.json|\.keras/.test(p))).toBe(false);
 await page.screenshot({path:'../.local/action-bot/model-release-admin.png',fullPage:true});
});
