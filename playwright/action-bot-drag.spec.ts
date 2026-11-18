import {test,expect} from '../frontend/node_modules/playwright/test';

test('dragging the launcher moves it without opening and keeps it reachable after resize',async({page})=>{
 await page.setViewportSize({width:1280,height:800});
 await page.goto('/action-bot-qa.html');
 const launcher=page.getByRole('button',{name:'Open action bot',exact:true});
 await expect(launcher).toBeVisible();
 const start=(await launcher.boundingBox())!;
 await page.mouse.move(start.x+start.width/2,start.y+start.height/2);
 await page.mouse.down();await page.mouse.move(300,200,{steps:12});await page.mouse.up();
 await expect(launcher).toHaveAttribute('aria-expanded','false');
 const moved=(await launcher.boundingBox())!;
 expect(moved.x).toBeLessThan(start.x-100);expect(moved.y).toBeLessThan(start.y-100);
 await launcher.click();await expect(page.getByRole('dialog',{name:'Action bot',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Close action bot',exact:true}).click();
 await page.mouse.move(moved.x+20,moved.y+20);await page.mouse.down();await page.mouse.move(1278,798,{steps:8});await page.mouse.up();
 await page.setViewportSize({width:320,height:568});
 await expect.poll(async()=>{const box=(await launcher.boundingBox())!;return box.x>=0&&box.y>=0&&box.x+box.width<=320&&box.y+box.height<=568}).toBe(true);
 await launcher.focus();await page.keyboard.press('Enter');
 await expect(page.getByRole('dialog',{name:'Action bot',exact:true})).toBeVisible();
});

test('touch dragging does not scroll or open the launcher',async({browser,baseURL})=>{
 const context=await browser.newContext({baseURL,viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 try{
  const page=await context.newPage();await page.goto('/action-bot-qa.html');
  const launcher=page.getByRole('button',{name:'Open action bot',exact:true});await expect(launcher).toBeVisible();
  const start=(await launcher.boundingBox())!,session=await context.newCDPSession(page);
  const point={x:start.x+start.width/2,y:start.y+start.height/2};
  await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
  await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:120,y:240}]});
  await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await expect(launcher).toHaveAttribute('aria-expanded','false');
  await expect.poll(async()=>Math.round((await launcher.boundingBox())!.x)).toBe(98);
  await launcher.tap();await expect(page.getByRole('dialog',{name:'Action bot',exact:true})).toBeVisible();
 }finally{await context.close()}
});
