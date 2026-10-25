import { test, expect } from '../frontend/node_modules/playwright/test';
import fixture from './fixtures/llama-reference.json';
import { authenticateAi } from './ai-test-utils';
import { readFileSync } from 'node:fs';

test('real pretrained TensorFlow.js worker generates without an external inference service',async({page})=>{
  test.skip(process.env.PMS_LLM_SMOKE!=='1','Opt-in: requires prepared 540 MB model assets.');
  test.setTimeout(600000);
  const external:string[]=[];
  page.on('console',message=>{if(message.text().startsWith('TF.js model backend:'))console.log(message.text());});
  page.on('request',r=>{if(!new URL(r.url()).hostname.match(/^(127\.0\.0\.1|localhost)$/))external.push(r.url());});
  await page.route('**/__llama_test.html',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Pretrained smoke</title>'}));
  await page.goto('/__llama_test.html');
  const instructions=readFileSync('../backend/app/ai_operator/brain_api.py','utf8').match(/INSTRUCTIONS = """([\s\S]*?)"""/)![1];
  const result=await page.evaluate(async instructions=>{
    const worker=new Worker('/src/lib/operator/localLLM.worker.ts',{type:'module'});
    let seq=0;
    const call=(type:string,payload:any={})=>new Promise<any>((resolve,reject)=>{
      const id=++seq;
      worker.onmessage=e=>{if(e.data.id!==id || e.data.progress)return;e.data.error?reject(new Error(e.data.error)):resolve(e.data.result);};
      worker.onerror=e=>reject(new Error(e.message));worker.postMessage({id,type,...payload});
    });
    try {
      const loaded=await call('load');
      console.log(`TF.js model backend: ${loaded.backend}`);
      const output=await call('generate',{messages:[
        {role:'system',content:instructions},
        {role:'user',content:'Prepare our release. Ask me for its deadline.'}]});
      return {loaded,output};
    }finally {worker.terminate();}
  },instructions);
  expect(result.output.stopped).toBe(true);
  const reply=JSON.parse(result.output.content);
  expect(reply.kind).toBe('ask');
  expect(reply.question).toMatch(/date|deadline|when|finish/i);
  expect(external).toEqual([]);
  console.log('Real TF.js pretrained smoke:',JSON.stringify(result));
});

test('TF.js decoder matches independent NumPy logits with full, chunked and cached attention', async ({page})=>{
  await page.route('**/__llama_test.html',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Decoder test</title>'}));
  await page.goto('/__llama_test.html');
  const result=await page.evaluate(async f=>{
    const path='/src/lib/operator/tfjsLlama.ts';
    const {TfjsLlama}=await import(/* @vite-ignore */path);
    // Import the same TF instance used by the decoder through Vite's resolver.
    const tfPath='/node_modules/.vite/deps/@tensorflow_tfjs.js';
    const tf=await import(/* @vite-ignore */tfPath);
    await tf.setBackend('cpu');await tf.ready();
    const weights=Object.fromEntries(Object.entries(f.weights).map(([name,value])=>[name,tf.tensor(value)]));
    const model=new TfjsLlama(f.config,weights),baseline=tf.memory().numTensors;
    const full=model.forward(f.ids);const values=Array.from(await full.data());full.dispose();model.reset();
    const parts:number[][]=[];
    for(const id of f.ids){const logits=model.forward([id]);parts.push(Array.from(await logits.data()));logits.dispose();}
    model.reset();
    const prefill=model.forward(f.ids.slice(0,2));prefill.dispose();
    const tail=model.forward(f.ids.slice(2));const chunked=Array.from(await tail.data());tail.dispose();model.reset();
    const after=tf.memory().numTensors;model.dispose();
    return {values,parts,chunked,leak:after-baseline};
  },fixture);
  for(let i=0;i<fixture.expected.length;i++)for(let j=0;j<fixture.expected[i].length;j++)expect(result.parts[i][j]).toBeCloseTo(fixture.expected[i][j],4);
  for(let j=0;j<result.values.length;j++){
    expect(result.values[j]).toBeCloseTo(fixture.expected.at(-1)![j],4);
    expect(result.chunked[j]).toBeCloseTo(result.values[j],4);
  }
  expect(result.leak).toBe(0);
});

test('browser LLM keeps follow-up memory local and uses cloud only after invalid local output',async({page})=>{
  await authenticateAi(page);
  let cloudCalls=0,turns:any[]=[],revision=0,generated=0;
  await page.addInitScript(()=>{
    const Original=window.Worker;
    window.Worker=class extends EventTarget {
      onmessage:any;onerror:any;
      constructor(url:any,options:any){super();if(!String(url).includes('localLLM.worker'))return new Original(url,options) as any;}
      postMessage(message:any){setTimeout(()=>{
        const payload=message.messages?JSON.parse(message.messages[1].content):{},command=payload.command || '';
        const remembered=payload.conversation?.some((turn:any)=>turn.assistant.question==='What is the deadline?');
        const reply=command==='Tomorrow' && remembered ? {kind:'answer',message:'Deadline noted from your follow-up.'} : {kind:'ask',message:'I can plan this.',question:'What is the deadline?'};
        this.onmessage?.({data:{id:message.id,result:message.type==='load'?{backend:'cpu'}:{content:command.includes('complex request')?'invalid JSON':JSON.stringify(reply),stopped:true}}});
      },0);}
      terminate(){}
    } as any;
  });
  await page.route('**/api/v1/**',async route=>{
    const p=new URL(route.request().url()).pathname,body=route.request().postDataJSON();
    const row={id:1,project_id:1,revision,turns};
    if(p.endsWith('/project-management/projects'))return route.fulfill({json:[{id:1,name:'Delivery',project_key:'WEB'}]});
    if(p.endsWith('/projects/1/tasks'))return route.fulfill({json:[]});
    if(p.endsWith('/ai-operator/providers'))return route.fulfill({json:{items:[{provider:'openai',enabled:true,data_sharing_allowed:true,has_key:true}]}});
    if(p.endsWith('/brain/sessions'))return route.fulfill({json:route.request().method()==='GET'?{items:[row]}:row});
    if(p.endsWith('/context'))return route.fulfill({json:{session:row,context:{tasks:[]},instructions:'Return PMS JSON',schema:{}}});
    if(p.endsWith('/validate')){generated++;return route.fulfill({json:body.reply});}
    if(p.endsWith('/turns')){turns.push({text:body.text,reply:body.reply,runtime:body.runtime});revision++;return route.fulfill({json:{...row,turns,revision}});}
    if(p.endsWith('/cloud')){cloudCalls++;return route.fulfill({json:{kind:'ask',message:'Cloud needs more context.',question:'Which milestone?'}});}
    return route.fulfill({json:{items:[]}});
  });
  await page.goto('/pms/operator');
  await page.getByRole('button',{name:'Load TensorFlow.js model'}).click();
  await expect(page.getByText('TensorFlow.js ready', {exact:false})).toBeVisible();
  await page.getByLabel('Local brain message').fill('Prepare release');await page.getByRole('button',{name:'Ask local brain'}).click();
  await expect(page.getByText('What is the deadline?',{exact:true})).toBeVisible();
  await page.getByLabel('Command',{exact:true}).fill('Tomorrow');await page.getByRole('button',{name:'Preview plan',exact:true}).click();
  await expect(page.getByText('Deadline noted from your follow-up.',{exact:false})).toBeVisible();
  expect(cloudCalls).toBe(0);expect(generated).toBe(2);
  await page.getByLabel('Local brain message').fill('complex request');await page.getByRole('button',{name:'Ask local brain'}).click();
  await expect(page.getByText('Which milestone?',{exact:true})).toBeVisible();
  expect(cloudCalls).toBe(1);
  await page.getByLabel('Use openai only when local reasoning', {exact:false}).uncheck();
  await page.getByLabel('Local brain message').fill('another complex request');
  await page.getByRole('button',{name:'Ask local brain'}).click();
  await expect(page.getByRole('alert')).toContainText('No LLM request was sent');
  expect(cloudCalls).toBe(1);
});
