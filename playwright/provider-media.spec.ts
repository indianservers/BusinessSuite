import {test,expect} from '../frontend/node_modules/playwright/test';

test('media grants save separately from the text model without inference or key disclosure',async({page})=>{
 await page.goto('/provider-media-qa.html');
 const area=page.getByRole('region',{name:'Gemini media capabilities',exact:true});
 await expect(area).toBeVisible();
 await expect(page.getByLabel('Model ID',{exact:true})).toHaveValue('existing-text-model');
 const image=page.getByLabel('Enable Gemini image processing',{exact:true});
 const audio=page.getByLabel('Enable Gemini transcription',{exact:true});
 await expect(image).not.toBeChecked();await expect(audio).not.toBeChecked();
 await image.check();await audio.check();await page.getByLabel('Gemini image model',{exact:true}).selectOption('gemini-3.1-flash-lite-image');
 await page.getByRole('button',{name:'Save settings',exact:true}).click();
 await expect(page.getByText('Provider settings saved.',{exact:false})).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__mediaRequests);
 const saved=requests.find((r:any)=>r.method==='put').body;
 expect(saved.model).toBe('existing-text-model');expect(saved.api_key).toBeUndefined();
 expect(saved.media).toEqual({image_enabled:true,image_model:'gemini-3.1-flash-lite-image',transcription_enabled:true,transcription_model:'gemini-3.5-flash-lite'});
 expect(requests.filter((r:any)=>r.method==='post')).toHaveLength(0);
 await expect(image).toBeChecked();await expect(audio).toBeChecked();
 await page.setViewportSize({width:390,height:844});await expect(area).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)).toBe(false);
});
