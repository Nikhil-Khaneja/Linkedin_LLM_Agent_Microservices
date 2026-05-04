from __future__ import annotations

import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

_named_param_re = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")

# ─── SQLite in-memory mode (APP_ENV=test) ────────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  payload_json TEXT,
  skills_json TEXT,
  experience_json TEXT,
  education_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
  refresh_token_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  is_revoked INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  expires_at TEXT
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
  idempotency_key TEXT PRIMARY KEY,
  route_name TEXT NOT NULL,
  body_hash TEXT NOT NULL,
  response_json TEXT,
  original_trace_id TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS members (
  member_id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  headline TEXT,
  about_text TEXT,
  location_text TEXT,
  profile_version INTEGER DEFAULT 1,
  is_deleted INTEGER DEFAULT 0,
  profile_views INTEGER NOT NULL DEFAULT 0,
  connections_count INTEGER NOT NULL DEFAULT 0,
  profile_photo_url TEXT,
  resume_url TEXT,
  resume_text TEXT,
  current_company TEXT,
  current_title TEXT,
  payload_json TEXT,
  skills_json TEXT,
  experience_json TEXT,
  education_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS recruiters (
  recruiter_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  phone TEXT,
  access_level TEXT,
  payload_json TEXT,
  skills_json TEXT,
  experience_json TEXT,
  education_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY,
  company_name TEXT NOT NULL,
  company_industry TEXT,
  company_size TEXT,
  payload_json TEXT,
  skills_json TEXT,
  experience_json TEXT,
  education_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  recruiter_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description_text TEXT NOT NULL,
  seniority_level TEXT,
  employment_type TEXT,
  location_text TEXT,
  work_mode TEXT,
  status TEXT DEFAULT 'open',
  version INTEGER DEFAULT 1,
  payload_json TEXT,
  skills_json TEXT,
  experience_json TEXT,
  education_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS applications (
  application_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  member_id TEXT NOT NULL,
  resume_ref TEXT,
  cover_letter TEXT,
  status TEXT DEFAULT 'submitted',
  application_datetime TEXT,
  payload_json TEXT,
  UNIQUE (job_id, member_id)
);
CREATE TABLE IF NOT EXISTS saved_jobs (
  save_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  member_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT,
  UNIQUE (job_id, member_id)
);
CREATE TABLE IF NOT EXISTS application_notes (
  note_id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL,
  recruiter_id TEXT NOT NULL,
  note_text TEXT NOT NULL,
  visibility TEXT DEFAULT 'internal',
  payload_json TEXT,
  skills_json TEXT,
  experience_json TEXT,
  education_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS outbox_events (
  outbox_id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  event_type TEXT NOT NULL,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  trace_id TEXT,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT DEFAULT 'pending',
  attempts INTEGER DEFAULT 0,
  error_message TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  published_at TEXT,
  available_at TEXT DEFAULT (datetime('now'))
);
CREATE VIEW IF NOT EXISTS recruiter_job_counts AS
  SELECT recruiter_id, COUNT(*) AS total_jobs FROM jobs GROUP BY recruiter_id;
CREATE VIEW IF NOT EXISTS member_application_counts AS
  SELECT member_id, COUNT(*) AS total_applications FROM applications GROUP BY member_id;
"""

_sqlite_conn: sqlite3.Connection | None = None
_sqlite_lock = threading.Lock()


def _is_test() -> bool:
    return os.environ.get('APP_ENV') == 'test'


def _dict_row_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _get_sqlite_conn() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        with _sqlite_lock:
            if _sqlite_conn is None:
                conn = sqlite3.connect(':memory:', check_same_thread=False)
                conn.row_factory = _dict_row_factory
                conn.execute('PRAGMA journal_mode=WAL')
                for stmt in _SQLITE_SCHEMA.split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        conn.execute(stmt)
                conn.commit()
                _sqlite_conn = conn
    return _sqlite_conn


# ─── MySQL helpers ───────────────────────────────────────────────────────────

def _db_config() -> dict[str, Any]:
    return {
        "host": os.environ.get("MYSQL_HOST", "host.docker.internal"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", "root"),
        "database": os.environ.get("MYSQL_DATABASE", "linkedin_sim"),
        "cursorclass": DictCursor,
        "autocommit": False,
        "charset": "utf8mb4",
        "connect_timeout": int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "10")),
        "read_timeout": int(os.environ.get("MYSQL_READ_TIMEOUT", "120")),
        "write_timeout": int(os.environ.get("MYSQL_WRITE_TIMEOUT", "120")),
    }


_pool: PooledDB | None = None
_pool_lock = threading.Lock()


def _get_pool() -> PooledDB:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                cfg = _db_config()
                cfg.pop("autocommit", None)  # PooledDB manages autocommit itself
                _pool = PooledDB(
                    creator=pymysql,
                    maxconnections=int(os.environ.get("MYSQL_POOL_MAX", "50")),
                    mincached=int(os.environ.get("MYSQL_POOL_MIN", "5")),
                    maxcached=20,
                    blocking=True,   # queue requests instead of crashing
                    ping=1,          # verify connection before handing out
                    **cfg,
                )
    return _pool


def connection():
    if _is_test():
        return None
    return _get_pool().connection()


def is_mysql() -> bool:
    return not _is_test()


@contextmanager
def cursor_ctx():
    if _is_test():
        conn = _get_sqlite_conn()
        with _sqlite_lock:
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
        return
    conn = connection()
    cur = None
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def _adapt_sql(query: str) -> str:
    if _is_test():
        # SQLite: normalize both forms to INSERT OR IGNORE INTO
        return query.replace('INSERT IGNORE INTO', 'INSERT OR IGNORE INTO')
    query = query.replace('INSERT OR IGNORE INTO', 'INSERT IGNORE INTO')
    return _named_param_re.sub(lambda m: f"%({m.group(1)})s", query)


def _params_for_query(query: str, params: dict[str, Any] | None):
    return params or {}


def fetch_one(query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with cursor_ctx() as cur:
        cur.execute(_adapt_sql(query), _params_for_query(query, params))
        row = cur.fetchone()
        return row if row else None


def fetch_all(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with cursor_ctx() as cur:
        cur.execute(_adapt_sql(query), _params_for_query(query, params))
        rows = cur.fetchall()
        return list(rows or [])


def execute(query: str, params: dict[str, Any] | None = None) -> int:
    with cursor_ctx() as cur:
        cur.execute(_adapt_sql(query), _params_for_query(query, params))
        return int(cur.rowcount or 0)


def execute_many(query: str, values: Iterable[dict[str, Any]]) -> int:
    values = list(values)
    if not values:
        return 0
    with cursor_ctx() as cur:
        cur.executemany(_adapt_sql(query), values)
        return int(cur.rowcount or 0)
