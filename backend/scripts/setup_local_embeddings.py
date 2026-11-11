"""Download pinned public model assets only. Never sends ERP text or secrets."""
import json,sys,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.ai_operator.local_embeddings import MODEL,REVISION,directory,verified


def main():
    folder=directory();folder.mkdir(parents=True,exist_ok=True)
    for remote,name,limit in [('onnx/model_quint8_avx2.onnx','model.onnx',24000000),('tokenizer.json','tokenizer.json',500000),('README.md','MODEL_CARD.md',50000)]:
        data=urllib.request.urlopen(f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{remote}',timeout=60).read(limit+1)
        if len(data)>limit:raise ValueError('Model asset exceeds expected size')
        tmp=folder/(name+'.pending');tmp.write_bytes(data);tmp.replace(folder/name)
    verified(folder)
    (folder/'provenance.json').write_text(json.dumps({'model':MODEL,'revision':REVISION,'license':'Apache-2.0','runtime':'onnxruntime CPU','pooling':'attention-mask mean, L2 normalization','max_tokens':256}),encoding='utf-8')
    print(json.dumps({'installed':True,'model':MODEL,'revision':REVISION,'server_only':True}))


if __name__=='__main__':main()
