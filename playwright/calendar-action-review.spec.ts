import {test,expect} from '../frontend/node_modules/playwright/test';

test('calendar action review shows time, private audience and sync effects; edits remain proposals',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?calendar=1');
 const review=page.getByRole('region',{name:'Calendar event changes',exact:true});
 await expect(review).toContainText('2026-12-01T09:00:00Z');
 await expect(review).toContainText('2026-12-01T10:00:00Z');
 await expect(review).toContainText('Owner private calendar');
 await expect(review).toContainText('Google calendar connection #7');
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await page.getByLabel('Step 1 title',{exact:true}).fill('Reviewed meeting title');
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 await expect(page.getByTestId('saved-revision')).toHaveText('[{"step":1,"field":"title","value":"Reviewed meeting title"}]');
 expect(writes).toEqual([]);
});
