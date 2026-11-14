import {test,expect} from '../frontend/node_modules/playwright/test';

for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
 test(`rebalance estimates remain review-only at ${viewport.width}px`,async({page})=>{
  await page.setViewportSize(viewport);
  const writes:string[]=[];
  page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
  await page.goto('/saved-view-review-qa.html?rebalance=1');
  const review=page.getByRole('region',{name:'Workload rebalance review',exact:true});
  await expect(review).toBeVisible();
  await expect(review).toContainText('Current assignees: #2');
  await expect(review).toContainText('Proposed assignees: #3');
  await expect(review).toContainText('Source load: 30 → 20 hours');
  await expect(review).toContainText('Recipient load: 5 → 15 hours');
  await expect(review).toContainText('Approval is required');
  await expect(review).toContainText('not a capacity reservation');
  expect(await review.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
  await page.screenshot({path:`../.local/rebalance-review-${viewport.width}.png`,fullPage:true});
  expect(writes).toEqual([]);
 });
}

test('stale projections are hidden in the workspace',async({page})=>{
 await page.goto('/saved-view-review-qa.html?rebalance=1&stale=1');
 await expect(page.getByRole('region',{name:'Workload rebalance review',exact:true})).toHaveCount(0);
});

test('provider-prepared recommendation uses the same server review card',async({page})=>{
 await page.goto('/saved-view-review-qa.html?rebalance=1&provider=1');
 const review=page.getByRole('region',{name:'Workload rebalance review',exact:true});
 await expect(review).toBeVisible();
 await expect(review).toContainText('Proposed assignees: #3');
 await expect(review).toContainText('Recipient load: 5 → 15 hours');
});

for(const waiting of [false,true]){
 test(`receipt-only workspace protects old history while ${waiting?'waiting':'completed'}`,async({page})=>{
  await page.setViewportSize({width:390,height:844});
  const writes:string[]=[];
  page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
  await page.goto('/saved-view-review-qa.html?restricted=1'+(waiting?'&waiting=1':''));
  const notice=page.getByRole('region',{name:'Receipt-only history notice',exact:true});
  await expect(notice).toContainText('New bot conversation');
  await expect(page.getByRole('tab',{name:'Review & edit',exact:true})).toBeDisabled();
  await expect(page.getByText('Help improve the bot',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Save edits for new review',exact:true})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Native task execution confirmed',exact:true})).toBeVisible();
  await expect(page.getByText('Execution receipt · succeeded',{exact:true})).toBeVisible();
  expect(await notice.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
  expect(writes).toEqual([]);
 });
}

test('restricted bot composer requires an explicit fresh conversation',async({page})=>{
 await page.goto('/action-bot-qa.html?path=/pms/tasks');
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot',exact:true});
 await expect(input).toBeEnabled();
 await input.fill('Show restricted completion');
 await page.getByRole('button',{name:'Send bot message',exact:true}).click();
 await expect(page.getByRole('region',{name:'Restricted conversation history',exact:true})).toBeVisible();
 await expect(input).toBeDisabled();
 await expect(page.getByRole('button',{name:'Review remaining tasks',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Approve these exact actions',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Start new conversation',exact:true}).click();
 await expect(input).toBeEnabled();
 await expect(input).toHaveValue('');
 await expect(page.getByRole('region',{name:'Restricted conversation history',exact:true})).toHaveCount(0);
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.filter((request:any)=>request.path.endsWith('/commands'))).toHaveLength(1);
 expect(requests.filter((request:any)=>/\/(approve|resume|feedback)$/.test(request.path))).toHaveLength(0);
});

test('restricted partial workflow exposes no old execution controls',async({page})=>{
 await page.goto('/action-bot-qa.html?path=/pms/tasks');
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot',exact:true});
 await expect(input).toBeEnabled();await input.fill('Show restricted partial workflow');
 await page.getByRole('button',{name:'Send bot message',exact:true}).click();
 await expect(page.getByRole('region',{name:'Restricted conversation history',exact:true})).toBeVisible();
 await expect(input).toBeDisabled();
 await expect(page.getByRole('button',{name:'Cancel remaining work',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Resume remaining reviewed actions',exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Start new conversation',exact:true})).toBeEnabled();
 await expect(page.getByRole('list',{name:'Workflow steps',exact:true}).getByRole('listitem')).toHaveCount(2);
 await expect(page.getByText('not confirmed',{exact:true})).toBeVisible();
 await page.getByRole('region',{name:'Restricted conversation history',exact:true}).getByRole('button',{name:'Review remaining tasks',exact:true}).click();
 await expect(input).toBeEnabled();
 await expect(input).toHaveValue('Review remaining PMS workflow #1');
 await expect(page.getByRole('region',{name:'Restricted conversation history',exact:true})).toHaveCount(0);
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.filter((request:any)=>request.path.endsWith('/commands'))).toHaveLength(1);
 expect(requests.filter((request:any)=>/\/(approve|resume|cancel|feedback)$/.test(request.path))).toHaveLength(0);
});

for(const differentProject of [false,true]){
 test(`workspace remaining-work starter respects project selection: ${differentProject?'different':'same'}`,async({page})=>{
  const writes:string[]=[];
  page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push(request.url())});
  await page.goto('/saved-view-review-qa.html?restricted=1&remaining=1'+(differentProject?'&differentProject=1':''));
  const button=page.getByRole('button',{name:'Review remaining tasks',exact:true});
  if(differentProject)await expect(button).toHaveCount(0);
  else{
   await button.click();
   await expect(page.getByTestId('saved-revision')).toContainText('Review remaining PMS workflow #');
  }
  expect(writes).toEqual([]);
 });
}
