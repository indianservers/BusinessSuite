"""Server-only sentence embeddings. No network, credentials, or document cache.

Inference runs in a small separate environment, keeping ML dependencies out of
the API environment. Model files are pinned and verified before every process.
"""
import hashlib,json,math,os,subprocess,threading
from pathlib import Path

MODEL='sentence-transformers/all-MiniLM-L6-v2'
REVISION='1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
MODEL_SHA256='b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21'
TOKENIZER_GIT_SHA='cb202bfe2e3c98645018a6d12f182a434c9d3e02'
MAX_TEXTS=201
_slots=threading.BoundedSemaphore(2)


def directory():
    from app.ai_operator.training_storage import root
    return root()/'embeddings'/'all-MiniLM-L6-v2'


def interpreter():
    default=Path(__file__).resolve().parents[3]/'.local'/'embedding-venv'
    return Path(os.environ.get('LOCAL_EMBEDDING_PYTHON') or default/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))


def verified(folder):
    folder=Path(folder)
    model=folder/'model.onnx';tokenizer=folder/'tokenizer.json'
    if not model.is_file() or model.stat().st_size!=23046789:raise ValueError('Embedding model unavailable')
    if hashlib.sha256(model.read_bytes()).hexdigest()!=MODEL_SHA256:raise ValueError('Embedding model checksum differs')
    data=tokenizer.read_bytes()
    if len(data)!=466247 or hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()!=TOKENIZER_GIT_SHA:
        raise ValueError('Embedding tokenizer checksum differs')
    return folder


def status():
    # Availability is inexpensive; checksum/inference errors are reported by the
    # actual search without sending paths or source content to the client.
    ready=interpreter().is_file() and (directory()/'model.onnx').is_file() and (directory()/'tokenizer.json').is_file()
    return {'available':ready,'model':MODEL,'revision':REVISION,'location':'server','dimensions':384,'language':'English semantic model; lexical matching also supports Unicode.'}


def encode(texts):
    if not isinstance(texts,list) or not 1<=len(texts)<=MAX_TEXTS or any(not isinstance(t,str) or len(t)>1600 for t in texts):
        raise ValueError('Embedding batch exceeds limits')
    if not _slots.acquire(timeout=2):raise ValueError('Embedding capacity busy')
    try:
        worker=Path(__file__).resolve().parents[2]/'scripts'/'embedding_worker.py'
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE','LANG','LC_ALL'}}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
        result=subprocess.run([str(interpreter()),'-I',str(worker),str(directory())],input=json.dumps({'texts':texts}),
            text=True,encoding='utf-8',capture_output=True,timeout=45,env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode or len(result.stdout)>3000000:raise ValueError('Local embedding inference unavailable')
        vectors=json.loads(result.stdout)['vectors']
        if len(vectors)!=len(texts) or any(not isinstance(v,list) or len(v)!=384 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) or abs(sum(x*x for x in v)-1)>.02 for v in vectors):
            raise ValueError('Invalid embedding response')
        return vectors
    except (OSError,subprocess.SubprocessError,KeyError,TypeError,json.JSONDecodeError):
        raise ValueError('Local embedding inference unavailable') from None
    finally:_slots.release()
