import {test,expect} from '../frontend/node_modules/playwright/test';

test('image instruction templates review text without copying pixels or calling a model',async({page})=>{
 await page.goto('/artifact-image-qa.html');
 await page.getByRole('button',{name:'Save image instructions as template',exact:true}).click();
 await page.getByLabel('Template content',{exact:true}).fill('A blue delivery van for {{customer}}. No text.');
 await page.getByLabel('Template image aspect ratio',{exact:true}).selectOption('16:9');
 await page.getByRole('button',{name:'Preview private template',exact:true}).click();
 await expect(page.getByRole('region',{name:'Exact artifact template review',exact:true})).toContainText('customer');
 const requests=await page.evaluate(()=>(window as any).__imageRequests);
 const preview=requests.find((r:any)=>r.path.endsWith('/artifact-templates/preview'));
 expect(preview.body.source_artifact_id).toBe(501);expect(preview.body.source_revision).toBe(2);
 expect(preview.body.body.kind).toBe('image_instruction');expect(preview.body.body.aspect_ratio).toBe('16:9');
 expect(preview.body.body.image).toBeUndefined();
 expect(requests.some((r:any)=>r.path.includes('/media/'))).toBe(false);
});

test('image share review waits for pixels and uses dedicated snapshot endpoints',async({page})=>{
 await page.goto('/artifact-image-qa.html?sharing');
 await page.getByRole('button',{name:'Share selected artifact version',exact:true}).click();
 await page.getByLabel('Artifact share member Synthetic reviewer',{exact:true}).check();
 await page.getByRole('button',{name:'Preview artifact share',exact:true}).click();
 const publish=page.getByRole('button',{name:'Publish this exact artifact and audience',exact:true});
 await expect(publish).toBeDisabled();
 await expect(page.getByRole('figure',{name:'Shared image 601 review position 0',exact:true}).getByRole('img')).toBeVisible();
 await expect(publish).toBeEnabled();await publish.click();
 await expect(page.getByRole('region',{name:'Artifact sharing preview',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Download shared PNG',exact:true})).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__imageRequests);
 expect(requests.some((r:any)=>r.path.endsWith('/artifact-shares/601/preview-image')&&r.params.preview_hash==='synthetic-review'&&r.responseType==='blob')).toBe(true);
 expect(requests.some((r:any)=>r.path.endsWith('/artifact-shares/601/image')&&r.params.revision===1)).toBe(true);
 expect(requests.some((r:any)=>r.path.includes('/artifacts/501/image'))).toBe(false);
});

test('private image previews use exact versions and clear after scope changes',async({page})=>{
 await page.goto('/artifact-image-qa.html');
 const image=page.getByRole('img',{name:'Synthetic private image',exact:true});
 await expect(image).toBeVisible();await expect(image).toHaveAttribute('src',/^blob:/);
 expect(await image.evaluate((value:HTMLImageElement)=>value.naturalWidth)).toBe(4);
 await page.getByLabel('Artifact 501 version',{exact:true}).selectOption('1');
 await expect(page.getByRole('figure',{name:'Image artifact 501 version 1',exact:true})).toBeVisible();
 await expect(image).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__imageRequests);
 expect(requests.filter((r:any)=>r.path.endsWith('/image')).map((r:any)=>r.params.revision)).toEqual([2,1]);
 expect(requests.filter((r:any)=>r.path.endsWith('/image')).every((r:any)=>r.responseType==='blob')).toBe(true);
 await expect(page.getByRole('button',{name:'Download PNG',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Download Word',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Save as template',exact:true})).toHaveCount(0);
 await page.evaluate(()=>window.dispatchEvent(new Event('suite:branch-changed')));
 await expect(image).toHaveCount(0);await expect(page.getByRole('alert')).toContainText('Access context changed');
});
