"""Create the standalone Inventory/POS PostgreSQL schema, without demo records."""
from pathlib import Path
from flask import Flask
from flask_migrate import upgrade
from app import create_database_if_missing
from app.extensions import db, migrate
from config import Config
import app.models

if __name__ == '__main__':
    create_database_if_missing(Config)
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    directory = str(Path(__file__).resolve().parent / 'migrations_postgresql')
    migrate.init_app(app, db, directory=directory)
    with app.app_context():
        upgrade()
    print('Inventory/POS PostgreSQL schema ready; no source data copied.')
