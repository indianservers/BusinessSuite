// Read-only numeric reference from the original TensorFlow.js architecture.
import * as tf from '@tensorflow/tfjs';
import {readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
const [folder,output]=process.argv.slice(2);
if(!folder||!output)throw new Error('Pass server model folder and reference output file');
const raw=await readFile(join(folder,'model.json')),bytes=await readFile(join(folder,'weights.bin'));
const json=JSON.parse(raw),metadata=json.userDefinedMetadata;
function tokens(text){return text.toLowerCase().replace(/\bkey [a-z][a-z0-9_-]*/g,'key slotkey').replace(/\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b/g,' slotuser ').replace(/\b[a-z][a-z0-9]*-\d+\b/g,' slotkey ').replace(/"[^"]*"/g,' slottext ').replace(/\b\d{4}-\d{2}-\d{2}\b/g,' slotdate ').replace(/\b\d+\b/g,' slotnumber ').match(/[a-z]+/g)||[];}
const corpus=JSON.parse(await readFile(new URL('../src/lib/operator/commandCorpus.json',import.meta.url)));
const texts=[...corpus.examples.map(e=>e.text),'set priority to High','meaningless quux zzz','"cancel all drafts"','assign tasks to "qa@example.test"','set due date to 2030-12-25','தமிழ் set priority high','priority １２３','key ABC-13'];
await tf.setBackend('cpu');await tf.ready();
const model=await tf.loadLayersModel(tf.io.fromMemory({modelTopology:json.modelTopology,weightSpecs:json.weightsManifest[0].weights,weightData:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}));
const xs=tf.tensor2d(texts.map(text=>{const words=new Set(tokens(text));return metadata.vocabulary.map(word=>words.has(word)?1:0);}));
const prediction=model.predict(xs),scores=await prediction.array();
const rows=texts.map((text,n)=>{const words=new Set(tokens(text)),known=[...words].filter(w=>metadata.vocabulary.includes(w)).length/Math.max(words.size,1);const order=scores[n].map((confidence,i)=>({confidence,intent:metadata.intents[i]})).sort((a,b)=>b.confidence-a.confidence);return {text,tokens:tokens(text),scores:scores[n],intent:order[0].intent,accepted:order[0].intent!=='fallback'&&order[0].confidence>=metadata.threshold&&order[0].confidence-order[1].confidence>=metadata.margin&&known>=.9};});
await writeFile(output,JSON.stringify({hashes:{'model.json':createHash('sha256').update(raw).digest('hex'),'weights.bin':createHash('sha256').update(bytes).digest('hex')},rows}));
tf.dispose([xs,prediction]);model.dispose();
console.log(JSON.stringify({reference_rows:rows.length,model_training_examples:metadata.trainingExamples,server_weights_only:true}));
