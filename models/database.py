import sqlite3
import os
import click
from flask import g, current_app

DATABASE = 'app.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config.get('DATABASE', DATABASE),
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

def executemany_db(query, args_list):
    db = get_db()
    db.executemany(query, args_list)
    db.commit()

def init_db():
    db = get_db()
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    # Migraciones para BDs existentes
    _run_migrations(db)
    db.commit()


def _run_migrations(db):
    """Migraciones idempotentes para BDs ya existentes."""
    migrations = [
        """CREATE TABLE IF NOT EXISTS company_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'viewer',
            modules TEXT DEFAULT 'all',
            invited_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(company_id, user_id)
        )""",
        "ALTER TABLE abc_models ADD COLUMN image_path TEXT",
        "ALTER TABLE cost_structures ADD COLUMN image_path TEXT",
    ]
    for sql in migrations:
        try:
            db.execute(sql)
        except Exception:
            pass  # Columna/tabla ya existe

def init_app(app):
    app.teardown_appcontext(close_db)
