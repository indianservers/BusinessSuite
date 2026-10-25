import * as tf from '@tensorflow/tfjs';
import { Tokenizer } from '@huggingface/tokenizers';
import { TfjsLlama } from './tfjsLlama';
import { setWasmPaths } from '@tensorflow/tfjs-backend-wasm';
import wasm from '@tensorflow/tfjs-backend-wasm/dist/tfjs-backend-wasm.wasm?url';
import simd from '@tensorflow/tfjs-backend-wasm/dist/tfjs-backend-wasm-simd.wasm?url';
import threaded from '@tensorflow/tfjs-backend-wasm/dist/tfjs-backend-wasm-threaded-simd.wasm?url';

let model:TfjsLlama|undefined, tokenizer:Tokenizer|undefined;
const root='/models/operator-llm/';
async function json(name:string) {const r=await fetch(root+name,{credentials:'omit'});if(!r.ok)throw new Error('Model assets missing. Run prepare:operator-llm first.');return r.json();}
self.onmessage=async(event:MessageEvent)=>{
  const {id,type,messages}=event.data;
  try {
    if(type==='load') {
      setWasmPaths({'tfjs-backend-wasm.wasm':wasm,'tfjs-backend-wasm-simd.wasm':simd,'tfjs-backend-wasm-threaded-simd.wasm':threaded});
      let selected=false;
      if(typeof OffscreenCanvas!=='undefined')try {selected=await tf.setBackend('webgl');}catch{/* Try local WASM next. */}
      if(!selected)try {selected=await tf.setBackend('wasm');}catch{/* Plain JS remains available. */}
      if(!selected)await tf.setBackend('cpu');
      await tf.ready();
      const manifest=await json('model.json');
      if(manifest.format!=='pms-tfjs-llama-v1' || manifest.userDefinedMetadata?.revision!=='12fd25f77366fa6b3b4b768ec3050bf629380bac')throw new Error('Unsupported model manifest');
      const [vocabulary,config]=await Promise.all([json('tokenizer.json'),json('tokenizer_config.json')]);
      tokenizer=new Tokenizer(vocabulary,config);
      const group=manifest.weightsManifest[0],buffers:ArrayBuffer[]=[];
      for(const [index,path] of group.paths.entries()) {
        if(!/^weights-\d{4}\.bin$/.test(path))throw new Error('Invalid weight path');
        const response=await fetch(root+path,{credentials:'omit'});if(!response.ok)throw new Error('Model shard missing');
        const buffer=await response.arrayBuffer();
        const checksum=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),b=>b.toString(16).padStart(2,'0')).join('');
        if(checksum!==manifest.userDefinedMetadata.sha256[path])throw new Error('Weight checksum mismatch');
        buffers.push(buffer);self.postMessage({id,progress:`Loading TensorFlow.js weights ${index+1}/${group.paths.length}`});
      }
      const data=tf.io.concatenateArrayBuffers(buffers);
      buffers.length=0;
      model=new TfjsLlama(manifest.modelTopology,tf.io.decodeWeights(data,group.weights));
      self.postMessage({id,result:{backend:tf.getBackend()}});
    }else if(type==='generate') {
      if(!model || !tokenizer)throw new Error('Model is not loaded');
      const chat=messages[0]?.role==='system'?messages:[{role:'system',content:'You are a helpful AI assistant named SmolLM, trained by Hugging Face'},...messages];
      // Assistant prefill discourages conversational prose in this JSON-only tool.
      const prefix='{"kind":';
      const prompt=chat.map((m:{role:string;content:string})=>`<|im_start|>${m.role}\n${m.content}<|im_end|>\n`).join('')+'<|im_start|>assistant\n'+prefix;
      const ids=tokenizer.encode(prompt,{add_special_tokens:false}).ids;
      const maxNew=768,maxContext=4096;
      if(ids.length+maxNew>maxContext){self.postMessage({id,error:'Local context exceeds 4096 tokens',reason:'context_limit'});return;}
      model.reset();const generated:number[]=[];
      let logits:tf.Tensor1D|undefined;
      try {
        for(let start=0;start<ids.length;start+=64){logits?.dispose();logits=model.forward(ids.slice(start,start+64));await new Promise(r=>setTimeout(r,0));}
        let stopped=false,content='';
        for(let step=0;step<maxNew;step++) {
          const choice=logits!.argMax();const next=(await choice.data())[0];choice.dispose();logits!.dispose();logits=undefined;
          if(next===2){stopped=true;break;}
          generated.push(next);
          content=prefix+tokenizer.decode(generated,{skip_special_tokens:true});
          // Stop at a complete JSON object instead of asking this small model
          // to spend more tokens generating a trailing explanation or EOS.
          try {const reply=JSON.parse(content);if(reply && typeof reply.kind==='string' && typeof reply.message==='string'){stopped=true;break;}}catch{/* Incomplete prefix */}
          logits=model.forward([next]);
          if(step%8===0)await new Promise(r=>setTimeout(r,0));
        }
        self.postMessage({id,result:{content:content || prefix,stopped}});
      }finally {logits?.dispose();model.reset();}
    }
  }catch(e){self.postMessage({id,error:e instanceof Error?e.message:'TensorFlow.js inference failed',reason:type==='load'?'unavailable':'invalid_output'});}
};
