"""One offline CPU generation. Prompts arrive on stdin, never command arguments."""
import json
from pathlib import Path
import sys


def main():
    model_folder=Path(sys.argv[1]).resolve();deps=Path(sys.argv[2]).resolve()
    if deps.is_dir():sys.path.insert(0,str(deps))
    structured=Path(sys.argv[3]).resolve()
    if structured.is_dir():sys.path.insert(0,str(structured))
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536:raise ValueError('Bounded input required')
    payload=json.loads(raw);messages=payload['messages']
    if len(messages)!=2 or [m['role'] for m in messages]!=['system','user']:raise ValueError('Invalid message envelope')
    import torch
    from transformers import AutoTokenizer,LlamaForCausalLM,StoppingCriteria,StoppingCriteriaList
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
    from importlib.metadata import version
    if version('lm-format-enforcer')!='0.11.3':raise ValueError('Unreviewed decoding runtime version')
    torch.set_num_threads(4)
    tokenizer=AutoTokenizer.from_pretrained(str(model_folder),local_files_only=True,trust_remote_code=False)
    model=LlamaForCausalLM.from_pretrained(str(model_folder),local_files_only=True,use_safetensors=True,torch_dtype=torch.float32).eval()
    prefix=''
    prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)+prefix
    ids=tokenizer.encode(prompt,return_tensors='pt',add_special_tokens=False)
    length=ids.shape[1];budget=768
    if length+budget>4096:
        print(json.dumps({'error':'context_limit'}));return
    def decoded(values):return prefix+tokenizer.decode(values[0,length:],skip_special_tokens=True)
    class CompleteJson(StoppingCriteria):
        def __call__(self,input_ids,scores,**kwargs):
            try:
                value=json.loads(decoded(input_ids));return isinstance(value,dict) and 'kind' in value and 'message' in value
            except ValueError:return False
    with torch.inference_mode():
        result=model.generate(ids,attention_mask=torch.ones_like(ids),max_new_tokens=budget,do_sample=False,
            pad_token_id=2,stopping_criteria=StoppingCriteriaList([CompleteJson()]),
            prefix_allowed_tokens_fn=build_transformers_prefix_allowed_tokens_fn(tokenizer,JsonSchemaParser(payload.get('schema'))))
    text=decoded(result)
    try:stopped=isinstance(json.loads(text),dict)
    except ValueError:stopped=False
    print(json.dumps({'content':text,'stopped':stopped},ensure_ascii=False))


if __name__=='__main__':main()
