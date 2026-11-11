"""Bounded stdin/stdout-only ONNX inference; no app imports, network or logs."""
import hashlib,json,sys
from pathlib import Path


def main():
    folder=Path(sys.argv[1]);model=folder/'model.onnx';tokenizer=folder/'tokenizer.json'
    # Pinned independently here: the isolated worker never imports app settings
    # or receives database/provider credentials in its environment.
    if model.stat().st_size!=23046789 or hashlib.sha256(model.read_bytes()).hexdigest()!='b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21':raise ValueError()
    raw=tokenizer.read_bytes()
    if len(raw)!=466247 or hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()!='cb202bfe2e3c98645018a6d12f182a434c9d3e02':raise ValueError()
    payload=sys.stdin.read(2000000);texts=json.loads(payload)['texts']
    if not isinstance(texts,list) or not 1<=len(texts)<=201 or any(not isinstance(t,str) or len(t)>1600 for t in texts):raise ValueError()
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(str(tokenizer));tok.enable_truncation(max_length=256);tok.enable_padding(pad_id=0,pad_token='[PAD]')
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.log_severity_level=3
    session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
    vectors=[]
    for start in range(0,len(texts),16):
        batch=tok.encode_batch(texts[start:start+16])
        ids=np.asarray([x.ids for x in batch],dtype=np.int64);mask=np.asarray([x.attention_mask for x in batch],dtype=np.int64)
        feed={'input_ids':ids,'attention_mask':mask,'token_type_ids':np.asarray([x.type_ids for x in batch],dtype=np.int64)}
        output=session.run(None,{x.name:feed[x.name] for x in session.get_inputs()})[0]
        expanded=mask[...,None].astype(np.float32)
        pooled=(output*expanded).sum(axis=1)/np.maximum(expanded.sum(axis=1),1e-9)
        pooled/=np.maximum(np.linalg.norm(pooled,axis=1,keepdims=True),1e-9)
        vectors.extend(pooled.tolist())
    sys.stdout.write(json.dumps({'vectors':vectors},allow_nan=False))


if __name__=='__main__':
    try:main()
    except Exception:
        # Never expose input text, filesystem details or model exceptions.
        sys.exit(1)
