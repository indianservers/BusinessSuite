import {test,expect} from '../frontend/node_modules/playwright/test';

test('PMS native view preview and staged rename use the existing review workspace',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?pms=1');
 const review=page.getByRole('region',{name:'Saved view changes',exact:true});
 await expect(review).toContainText('Current: High');await expect(review).toContainText('Proposed: Low');
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await page.getByLabel('Step 1 name',{exact:true}).fill('PMS reviewed focus');
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 await expect(page.getByTestId('saved-revision')).toHaveText('[{"step":1,"field":"name","value":"PMS reviewed focus"}]');
 expect(writes).toEqual([]);
});
test('saved view changes show native before/after values and name edits remain a review',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html');
 const review=page.getByRole('region',{name:'Saved view changes',exact:true});
 await expect(review).toContainText('Current: High');await expect(review).toContainText('Proposed: Low');
 await expect(review).toContainText('abcdefabcdefabcdefabcdefabcdefab');
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await page.getByLabel('Step 1 name',{exact:true}).fill('Reviewed focus');
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 await expect(page.getByTestId('saved-revision')).toContainText('Reviewed focus');expect(writes).toEqual([]);
});


test('dependent view changes show projected before values and edit the selected step only',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?chain=1');
 const review=page.getByRole('region',{name:'Saved view changes',exact:true});
 await expect(review).toContainText('Current: Low');await expect(review).toContainText('Proposed: Medium');
 await expect(page.getByLabel('Workspace workflow steps',{exact:true})).toContainText('After step 1');
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await page.getByLabel('Step 2 name',{exact:true}).fill('Edited second step');
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 await expect(page.getByTestId('saved-revision')).toHaveText('[{"step":2,"field":"name","value":"Edited second step"}]');
 expect(writes).toEqual([]);
});
