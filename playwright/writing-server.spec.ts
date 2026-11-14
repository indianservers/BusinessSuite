import {test,expect} from '../frontend/node_modules/playwright/test';

test('writing stays server-side and requires explicit cloud regeneration and insertion',async({page})=>{
 const modelRequests:string[]=[];page.on('request',r=>{if(/\/models\/|localLLM\.worker|commandRouter\.worker/.test(r.url()))modelRequests.push(r.url());});
 await page.goto('/writing-server-qa.html');
 await page.getByLabel('Original notes').focus();
 await page.getByRole('button',{name:'Improve writing',exact:true}).click();
 await expect(page.getByLabel('AI generated draft')).toHaveValue('Local draft R-742');
 const provider=page.getByLabel('AI writing provider');
 await expect(provider.locator('option')).toHaveCount(2);
 await provider.selectOption('gemini');
 await expect(page.getByLabel('AI generated draft')).toHaveCount(0);
 let calls=await page.evaluate(()=>(window as any).__writingRequests.filter((r:any)=>r.url.endsWith('/writing/draft')));
 expect(calls).toHaveLength(1);expect(calls[0].body.provider).toBe('local');expect(calls[0].body.workspace_id).toBe(7);
 await page.getByRole('button',{name:'Regenerate',exact:true}).click();
 await expect(page.getByLabel('AI generated draft')).toHaveValue('Server Gemini draft R-742');
 await expect(page.getByLabel('Original notes')).toHaveValue('Review R-742 Friday.');
 await page.getByRole('button',{name:'Insert into editor',exact:true}).click();
 await expect(page.getByLabel('Original notes')).toHaveValue('Server Gemini draft R-742');
 calls=await page.evaluate(()=>(window as any).__writingRequests.filter((r:any)=>r.url.endsWith('/writing/draft')));
 expect(calls).toHaveLength(2);expect(calls[1].body.provider).toBe('gemini');
 expect(modelRequests).toEqual([]);
});

test('an edited source is not overwritten by a stale draft',async({page})=>{
 await page.goto('/writing-server-qa.html');await page.getByLabel('Original notes').focus();
 await page.getByRole('button',{name:'Improve writing',exact:true}).click();
 await expect(page.getByLabel('AI generated draft')).toHaveValue('Local draft R-742');
 await page.evaluate(()=>{(document.querySelector('[aria-label="Original notes"]') as HTMLTextAreaElement).value='New source edit';});
 await page.getByRole('button',{name:'Insert into editor',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('original field changed');
 await expect(page.getByLabel('Original notes')).toHaveValue('New source edit');
});
