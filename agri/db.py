"""SQLite persistence (users, crop analyses, irrigation plans)."""
import json
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    phone           TEXT,
    farm_name       TEXT,
    location_name   TEXT,
    lat             REAL,
    lon             REAL,
    default_crop    TEXT DEFAULT 'tomato',
    default_soil    TEXT DEFAULT 'loamy',
    default_method  TEXT DEFAULT 'drip',
    area_acres      REAL DEFAULT 1.0,
    pump_hp         REAL DEFAULT 5.0,
    pump_head_m     REAL DEFAULT 20.0,
    tariff          REAL DEFAULT 6.0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    image_file      TEXT NOT NULL,
    crop            TEXT NOT NULL,
    stage           TEXT NOT NULL,
    soil            TEXT NOT NULL,
    location_name   TEXT,
    lat             REAL,
    lon             REAL,
    status          TEXT NOT NULL,
    disease_key     TEXT,
    confidence      REAL,
    report_json     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS irrigation_plans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    crop            TEXT NOT NULL,
    stage           TEXT NOT NULL,
    soil            TEXT NOT NULL,
    location_name   TEXT,
    lat             REAL,
    lon             REAL,
    status          TEXT NOT NULL,
    water_saved_l   REAL DEFAULT 0,
    energy_saved_kwh REAL DEFAULT 0,
    result_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_plans_user ON irrigation_plans(user_id, created_at);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
    app.teardown_appcontext(close_db)


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def loads(text):
    return json.loads(text) if text else None


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)
