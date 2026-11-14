import {test,expect} from '../frontend/node_modules/playwright/test';

test('time review shows exact minutes and Pending effects; inline edits remain proposals',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?time=1');
 const review=page.getByRole('region',{name:'Time entry changes',exact:true});
 await expect(review).toContainText('45');await expect(review).toContainText('90');
 await expect(review).toContainText('Current user only');
 await expect(review).toContainText('does not approve a timesheet or invoice the customer');
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await page.getByLabel('Step 1 duration_minutes',{exact:true}).fill('75');
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 await expect(page.getByTestId('saved-revision')).toHaveText('[{"step":1,"field":"duration_minutes","value":75}]');
 expect(writes).toEqual([]);
});
