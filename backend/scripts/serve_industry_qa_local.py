"""Owned loopback QA API over the existing local company databases; workers off."""
import json
import asyncio
import os
from pathlib import Path
import socket
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.qa_industry_companies_local import local_guard, ROOT
local_guard()
from app.main import app
from app.core.config import settings
import uvicorn
settings.EMAIL_NOTIFICATIONS_ENABLED = False
sock = socket.socket()
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
path = ROOT / '.local/industry-qa15/api.json'
path.write_text(json.dumps({'origin': f'http://127.0.0.1:{port}', 'pid': os.getpid()}), encoding='utf-8')
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
uvicorn.Server(uvicorn.Config(app, loop='none', lifespan='off', log_level='warning', access_log=False)).run(sockets=[sock])
