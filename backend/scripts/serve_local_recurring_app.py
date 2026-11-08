"""Serve current source against the existing local DB, without seed/migration startup."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from sqlalchemy.engine import make_url
target = make_url(settings.SQLALCHEMY_DATABASE_URI)
if target.get_backend_name() != 'sqlite' and target.host not in {'localhost', '127.0.0.1', '::1'}:
    raise RuntimeError('Local development server requires a loopback database')
if settings.SERVERLESS or settings.ENVIRONMENT.lower() == 'production':
    raise RuntimeError('Local development server cannot use production configuration')
from app.main import app
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001, lifespan='off')
