"""Keep secondary factories from silently escaping disposable test storage."""
import os
from pathlib import Path
from tempfile import gettempdir
from app.db.session import engine
from app.main import app


def test_secondary_database_factory_is_disposable(client,db):
    from app.core.config import settings
    from dotenv import dotenv_values
    configured=dotenv_values(Path(__file__).resolve().parents[1]/'.env')
    assert settings.SECRET_KEY!=configured.get('SECRET_KEY')
    assert settings.REFRESH_SECRET_KEY!=configured.get('REFRESH_SECRET_KEY')
    assert settings.SECRET_KEY_PREVIOUS==settings.REFRESH_SECRET_KEY_PREVIOUS==''
    assert settings.STORAGE_BACKEND=='local'
    assert settings.OPENAI_API_KEY==''
    assert settings.S3_ACCESS_KEY_ID==settings.S3_SECRET_ACCESS_KEY==settings.BLOB_READ_WRITE_TOKEN==''
    if os.environ.get('TEST_DATABASE_URL'):
        assert engine.url.get_backend_name()=='postgresql'
        assert engine.url.database.endswith('_test')
    else:
        assert engine.url.get_backend_name()=='sqlite'
        path=Path(engine.url.database).resolve()
        assert path.is_relative_to(Path(gettempdir()).resolve())
        assert path.parent.name.startswith('business-suite-test-factories-')
    assert app.state.audit_session_factory() is db
    assert app.state.audit_close_session is False
    assert app.state.audit_commit is False
