import * as tf from '@tensorflow/tfjs-core';
import { loadLayersModel, type LayersModel } from '@tensorflow/tfjs-layers';
import '@tensorflow/tfjs-backend-cpu';
import { tokens } from './localCommands';

type Artifact = { version: number; vocabulary: string[]; intents: string[];
  trainingExamples: number; threshold: number; margin: number };
let artifact: Artifact;
let model: LayersModel;
let ready: Promise<void> | undefined;
async function initialize() {
  await tf.setBackend('cpu'); await tf.ready();
  model = await loadLayersModel(`${import.meta.env.BASE_URL}models/operator/model.json`);
  artifact = model.getUserDefinedMetadata() as Artifact;
  if (artifact.version !== 3 || artifact.trainingExamples < 100) { model.dispose(); throw new Error('Model version mismatch'); }

}
self.onmessage = async (event: MessageEvent<{ id: number; clauses: string[] }>) => {
  const { id, clauses } = event.data;
  try {
    ready ||= initialize(); await ready;
    const predictions = clauses.map(text => tf.tidy(() => {
      const words = new Set(tokens(text));
      const features = artifact.vocabulary.map(w => words.has(w) ? 1 : 0);
      const probabilities = (model.predict(tf.tensor2d([features])) as tf.Tensor).dataSync();
      const sorted = Array.from(probabilities).map((confidence, i) => ({ confidence, intent: artifact.intents[i] })).sort((a,b) => b.confidence-a.confidence);
      const known = [...words].filter(w => artifact.vocabulary.includes(w)).length / Math.max(words.size, 1);
      return { ...sorted[0], accepted: sorted[0].intent !== 'fallback' && sorted[0].confidence >= artifact.threshold &&
        sorted[0].confidence-sorted[1].confidence >= artifact.margin && known >= 0.9 };
    }));
    self.postMessage({ id, predictions, trainingExamples: artifact.trainingExamples });
  } catch { ready = undefined; self.postMessage({ id, error: 'Local model unavailable. Choose cloud planning to continue.' }); }
};
