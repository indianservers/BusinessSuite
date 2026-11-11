import { BROWSER_MODELS, generateLocalWriting, loadBrowserBrain } from './localLLM';

/** Writing and chat share the operator's existing local weights and worker. */
export async function writeWithLocalBrain(action:string,text:string,tone:string,language:string,progress:(text:string)=>void,signal:AbortSignal) {
  if(text.length>7000)throw new Error('The local language model accepts up to 7,000 source characters. Narrow the selected text and retry.');
  await loadBrowserBrain(BROWSER_MODELS[0].id,progress,signal);
  if(signal.aborted)throw new DOMException('Cancelled','AbortError');
  progress('Writing with the local agent model…');
  const instruction=action==='translate'?`Translate the source to ${language}. Return only the translated text as message. If unable to translate, say so explicitly.`:action==='tone'?`Rewrite the source in a ${tone} tone. Preserve all factual details.`:'Improve clarity, grammar and wording. Preserve all factual details.';
  const examples:Record<string,{source:string;result:string}>={
    french:{source:'Hello.',result:'Bonjour.'},hindi:{source:'Hello.',result:'नमस्ते।'},telugu:{source:'Hello.',result:'నమస్కారం.'},
    spanish:{source:'Hello.',result:'Hola.'},german:{source:'Hello.',result:'Hallo.'},tamil:{source:'Hello.',result:'வணக்கம்.'},
  };
  return generateLocalWriting(instruction,text,signal,action==='translate'?examples[language.toLowerCase()]:undefined);
}
