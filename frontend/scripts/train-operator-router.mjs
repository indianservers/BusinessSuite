// Reproducible, offline training: no business text or provider API calls.
import * as tf from '@tensorflow/tfjs';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
await import('./expand-operator-corpus.mjs');
const corpus = JSON.parse(await readFile(new URL('../src/lib/operator/commandCorpus.json', import.meta.url)));
function tokens(text) {
  return text.toLowerCase().replace(/\bkey [a-z][a-z0-9_-]*/g, 'key slotkey').replace(/\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b/g, ' slotuser ').replace(/\b[a-z][a-z0-9]*-\d+\b/g, ' slotkey ').replace(/"[^"]*"/g, ' slottext ').replace(/\b\d{4}-\d{2}-\d{2}\b/g, ' slotdate ')
    .replace(/\b\d+\b/g, ' slotnumber ').match(/[a-z]+/g) || [];
}
const vocabulary = [...new Set(corpus.examples.flatMap(e => tokens(e.text)))].sort();
const intents = [...new Set(corpus.examples.map(e => e.intent))].sort();
const features = text => { const words = new Set(tokens(text)); return vocabulary.map(w => words.has(w) ? 1 : 0); };
const xs = tf.tensor2d(corpus.examples.map(e => features(e.text)));
const ys = tf.tensor2d(corpus.examples.map(e => intents.map(i => i === e.intent ? 1 : 0)));
const model = tf.sequential();
model.add(tf.layers.dense({ inputShape: [vocabulary.length], units: intents.length, activation: 'softmax',
  kernelInitializer: tf.initializers.glorotUniform({ seed: 37 }) }));
model.compile({ optimizer: tf.train.adam(0.04), loss: 'categoricalCrossentropy', metrics: ['accuracy'] });
await model.fit(xs, ys, { epochs: 400, batchSize: corpus.examples.length, shuffle: false, verbose: 0 });
const predicted = model.predict(xs);
const data = await predicted.array();
const accuracy = data.filter((p, n) => intents[p.indexOf(Math.max(...p))] === corpus.examples[n].intent).length / data.length;
if (accuracy < 0.98) throw new Error(`Training accuracy ${accuracy} below release threshold`);
const minimumConfidence = Math.min(...data.filter((_,i) => corpus.examples[i].intent !== 'fallback').map((p) => Math.max(...p)));
if (minimumConfidence < 0.90) throw new Error(`Training confidence ${minimumConfidence} below local routing threshold`);
const metadata = { version: corpus.version, vocabulary, intents,
  trainingExamples: corpus.examples.length, trainingAccuracy: accuracy, threshold: 0.90, margin: 0.35 };
const output = new URL('../public/models/operator/', import.meta.url);
await mkdir(output, { recursive: true });
await model.save(tf.io.withSaveHandler(async artifacts => {
  const weights = artifacts.weightData instanceof ArrayBuffer ? Buffer.from(artifacts.weightData) : Buffer.concat(artifacts.weightData.map(b => Buffer.from(b)));
  await writeFile(new URL('weights.bin', output), weights);
  await writeFile(new URL('model.json', output), JSON.stringify({ format: 'layers-model', generatedBy: artifacts.generatedBy,
    convertedBy: null, modelTopology: artifacts.modelTopology,
    weightsManifest: [{ paths: ['weights.bin'], weights: artifacts.weightSpecs }], userDefinedMetadata: metadata }));
  return { modelArtifactsInfo: { dateSaved: new Date(), modelTopologyType: 'JSON', weightDataBytes: weights.byteLength } };
}));
// Verify standard serialization preserves predictions before publishing it.
const json = JSON.parse(await readFile(new URL('model.json', output)));
const bytes = await readFile(new URL('weights.bin', output));
const loaded = await tf.loadLayersModel(tf.io.fromMemory({ modelTopology: json.modelTopology,
  weightSpecs: json.weightsManifest[0].weights, weightData: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) }));
const reloaded = loaded.predict(xs);
const maxDifference = tf.tidy(() => predicted.sub(reloaded).abs().max().dataSync()[0]);
if (maxDifference > 0.000001) throw new Error('Saved weights failed prediction roundtrip');
console.log(`Saved standard model.json + weights.bin: ${metadata.trainingExamples} examples, ${intents.length} intents, training accuracy ${accuracy}.`);
tf.dispose([xs, ys, predicted, reloaded]); loaded.dispose(); model.dispose();
