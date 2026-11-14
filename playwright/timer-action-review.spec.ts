import {test,expect} from '../frontend/node_modules/playwright/test';

test('timer discard review shows loss of unrecorded time without making writes',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?timer=1');
 const review=page.getByRole('region',{name:'Timer changes',exact:true});
 await expect(review).toContainText('Your native timer');
 await expect(review).toContainText('unrecorded elapsed time is discarded');
 await expect(review).toContainText('without creating a time entry');
 expect(writes).toEqual([]);
});

test('timer start description edits remain proposals and session identity is read-only',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?timerStart=1');
 await expect(page.getByRole('region',{name:'Timer changes',exact:true})).toContainText('Starts when executed on the server');
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await page.getByLabel('Step 1 description',{exact:true}).fill('Reviewed timer intention');
 await expect(page.getByRole('textbox',{name:'Step 1 session_key',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 await expect(page.getByTestId('saved-revision')).toHaveText('[{"step":1,"field":"description","value":"Reviewed timer intention"}]');
 expect(writes).toEqual([]);
});
