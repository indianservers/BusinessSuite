import {test,expect} from '../frontend/node_modules/playwright/test';

test('platform training distinguishes fine tuning from separate dialogue checks',async({page})=>{
 await page.goto('/platform-nlp-qa.html');
 await expect(page.getByRole('status')).toContainText('Training stage: release blocked');
 const checks=page.getByRole('region',{name:'Dialogue checks for run 244',exact:true});
 await expect(checks).toContainText('Fine-tuned from verified run #243.');
 await expect(checks).toContainText('Seen training examples: 99.8%');
 await expect(checks).toContainText('Authored development wording: 95.9%');
 await expect(checks).toContainText('Separate workplace probes: 81/90 correct');
 await expect(checks).toContainText('450 curated workplace dialogue turns');
 await expect(checks).toContainText('do not measure production accuracy');
 await expect(page.getByRole('button',{name:'Activate model #244',exact:true})).toBeDisabled();
 expect(await page.evaluate(()=>(window as any).__platformNlpRequests.some((path:string)=>/bundle\.json|\.keras|\/activate$/.test(path)))).toBe(false);
});
