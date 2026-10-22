import os
from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('INVENTORY_DATABASE_URL') or URL.create(
        'postgresql+psycopg', username=os.environ.get('POSTGRES_USER', 'business_suite'),
        password=os.environ.get('POSTGRES_PASSWORD', ''), host=os.environ.get('POSTGRES_SERVER', '127.0.0.1'),
        port=int(os.environ.get('POSTGRES_PORT', '5432')), database=os.environ.get('INVENTORY_POSTGRES_DB', 'business_suite_inventory'),
        query={'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer')},
    ).render_as_string(hide_password=False)
    if make_url(SQLALCHEMY_DATABASE_URI).get_backend_name() not in {'postgresql', 'postgres'}:
        raise ValueError('Inventory requires a PostgreSQL connection')
    SQLALCHEMY_DATABASE_URI = make_url(SQLALCHEMY_DATABASE_URI).set(drivername='postgresql+psycopg').render_as_string(hide_password=False)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_TIME_LIMIT = 3600

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URI', 'sqlite:///:memory:')

config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    env = os.environ.get('APP_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)
