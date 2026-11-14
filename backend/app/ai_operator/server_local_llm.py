"""Bounded offline generation from a fixed private model, never a browser model."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from fastapi import HTTPException

MODEL='SmolLM2-135M-Instruct-server'
REVISION='12fd25f77366fa6b3b4b768ec3050bf629380bac'
HASHES={'config.json':'8eb740e8bbe4cff95ea7b4588d17a2432deb16e8075bc5828ff7ba9be94d982a',
 'model.safetensors':'5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c',
 'tokenizer.json':'9ca9acddb6525a194ec8ac7a87f24fbba7232a9a15ffa1af0c1224fcd888e47c',
 'tokenizer_config.json':'4ec77d44f62efeb38d7e044a1db318f6a939438425312dfa333b8382dbad98df'}
_busy=Lock()


def folder():
    from app.ai_operator.training_storage import root
    return root().parent/'generative/SmolLM2-135M-Instruct'


def dependencies():
    return Path(os.environ.get('LOCAL_GENERATIVE_DEPENDENCIES') or Path(__file__).resolve().parents[3]/'.local/llm-validation-deps').resolve()


def structured_dependencies():return folder().parents[1]/'runtime/structured-output'


def status():
    installed=all((folder()/name).is_file() for name in HASHES)
    available=installed and all((dependencies()/name).is_dir() for name in ('torch','transformers')) and (structured_dependencies()/'lmformatenforcer').is_dir()
    return {'model':MODEL,'revision':REVISION,'runtime':'server','installed':installed,'available':available,'output_format':'json-schema',
        'cloud_calls':0,'limits':'Small pretrained generative model; outputs require native validation and review. TensorFlow action classifiers are separate. No automatic cloud fallback.'}


def verify():
    for name,expected in HASHES.items():
        with (folder()/name).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Model integrity mismatch')


def generate(messages,seconds=45,*,schema=None):
    if not _busy.acquire(blocking=False):raise HTTPException(409,'LOCAL_MODEL_BUSY')
    try:
        verify()
        payload=json.dumps({'messages':messages,'schema':schema},ensure_ascii=False).encode('utf-8')
        if len(payload)>60000:raise HTTPException(422,'LOCAL_MODEL_CONTEXT_LIMIT')
        env={key:value for key,value in os.environ.items() if key.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE'}}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',PYTHONIOENCODING='utf-8')
        worker=Path(__file__).resolve().parents[2]/'scripts/server_local_llm_worker.py'
        flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        # Windows venv python.exe is a launcher which creates another process.
        # Launch the interpreter itself so timeout kills the CPU worker, not only
        # that launcher. Dependencies are supplied explicitly by the worker.
        python=getattr(sys,'_base_executable',sys.executable) if os.name=='nt' else sys.executable
        structured=structured_dependencies()
        result=subprocess.run([python,'-I',str(worker),str(folder()),str(dependencies()),str(structured)],input=payload,
            capture_output=True,env=env,timeout=max(1,min(45,seconds)),**flags)
        if result.returncode or len(result.stdout)>262144:raise HTTPException(503,'LOCAL_MODEL_UNAVAILABLE')
        data=json.loads(result.stdout)
        if data.get('error')=='context_limit':raise HTTPException(422,'LOCAL_MODEL_CONTEXT_LIMIT')
        if not data.get('stopped'):raise HTTPException(422,'LOCAL_MODEL_INVALID_OUTPUT')
        value=json.loads(data['content'])
        if not isinstance(value,dict):raise ValueError('Object required')
        return value
    except subprocess.TimeoutExpired:raise HTTPException(504,'LOCAL_MODEL_TIMEOUT') from None
    except (OSError,ValueError,KeyError,TypeError):raise HTTPException(503,'LOCAL_MODEL_UNAVAILABLE') from None
    finally:_busy.release()
