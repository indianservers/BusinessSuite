import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
const browser=await chromium.launch();
const results=[];
try{
 const page=await browser.newPage();page.on('console',message=>{if(message.text().startsWith('WRITING_MODEL'))console.log(message.text())});
 await page.goto('http://127.0.0.1:5192/login');
 for(const item of [{action:'improve',text:'Please review renewal R-742. The amount is INR 12750.',language:'English'},
                    {action:'tone',text:'Send the renewal details ASAP.',language:'English'},
                    {action:'translate',text:'Hello, thank you for your message.',language:'French'}]){
   console.log('CHECK',item.action);
   const result=await page.evaluate(async item=>{
     const {writeWithLocalBrain}=await import('/src/lib/operator/localWriting.ts');
     try{return {text:await writeWithLocalBrain(item.action,item.text,'professional',item.language,text=>console.log('WRITING_MODEL '+text),new AbortController().signal)}}catch(e){return {error:e.message}}
   },item);
   if(result.error?.includes('changed a source number or date')){result.guardPassed=true;delete result.error;}
   console.log(JSON.stringify(result));results.push({...item,...result});
 }
 await mkdir('../.local/page-ai-actions',{recursive:true});await writeFile('../.local/page-ai-actions/model-results.json',JSON.stringify(results,null,2));
 if(results.some(r=>r.error))throw Error('Local model writing failed');
}finally{await browser.close()}
