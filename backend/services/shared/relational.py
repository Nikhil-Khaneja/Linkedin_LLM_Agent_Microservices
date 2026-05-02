from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Any, Iterable

import pymysql
from pymysql.cursors import DictCursor

_named_param_re = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


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
    }


def connection():
    return pymysql.connect(**_db_config())


def is_mysql() -> bool:
    return True


@contextmanager
def cursor_ctx():
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
