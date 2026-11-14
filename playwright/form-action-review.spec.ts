import {test,expect} from '../frontend/node_modules/playwright/test';
test('native form preview remains closed and question editing saves only a fresh review',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?form=create');
 const review=page.getByRole('region',{name:'Native form review',exact:true});
 await expect(review).toContainText('closed, unpublished');await expect(review).toContainText('Anyone with the public link');
 await expect(review.getByRole('button',{name:/^Send request/})).toBeDisabled();
 await expect(review.getByText('Edit form questions',{exact:true})).toHaveCount(0);
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await review.getByText('Edit form questions',{exact:true}).click();
 await expect(review.getByRole('button',{name:'Publishing settings',exact:true})).toHaveCount(0);
 await review.getByRole('button',{name:/Short text/}).click();
 await expect(page.getByRole('button',{name:'Save edits for new review',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 await expect.poll(async()=>JSON.parse(await page.getByTestId('saved-revision').innerText()).find((change:any)=>change.field==='fields')?.value.length).toBe(4);
 expect(writes).toEqual([]);
});

test('publication review shows its audience and cannot edit or submit the published form',async({page})=>{
 const writes:string[]=[];page.on('request',request=>{if(['POST','PUT','DELETE'].includes(request.method()))writes.push(request.url())});
 await page.goto('/saved-view-review-qa.html?form=publish');
 const review=page.getByRole('region',{name:'Native form review',exact:true});
 await expect(review).toContainText('Form #42');await expect(review).toContainText('Approving this action publishes this exact saved draft');
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 await expect(review.getByText('Edit form questions',{exact:true})).toHaveCount(0);
 await expect(review.getByRole('button',{name:/^Send request/})).toBeDisabled();expect(writes).toEqual([]);
});
