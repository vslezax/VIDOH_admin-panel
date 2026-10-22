"""
Работа с PostgreSQL (Neon) для консольных скриптов.

Тонкая обёртка над psycopg2: подключение из DATABASE_URL,
хелперы для выборок/исполнения и метаданных схемы.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parent.parent


def get_database_url() -> str:
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(f"DATABASE_URL не найден. Проверьте файл {ROOT / '.env'}")
    return url


def connect() -> "psycopg2.extensions.connection":
    conn = psycopg2.connect(get_database_url())
    conn.autocommit = True
    return conn


def scalarize(value: Any) -> Any:
    """Приводит значение БД к удобочитаемому виду для консоли."""
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:g}"
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (dict, list)):
        import json
        return json.dumps(value, ensure_ascii=False)
    return value


def query(
    conn,
    sql: str,
    params: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        return [{k: scalarize(v) for k, v in row.items()} for row in cur.fetchall()]


def execute(conn, sql: str, params: Sequence[Any] | None = None) -> int:
    with conn.cursor() as cur:
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        return cur.rowcount


def quote_ident(name: str) -> str:
    """Безопасное экранирование идентификатора (таблица/колонка)."""
    return '"' + name.replace('"', '""') + '"'


# --- Метаданные схемы -------------------------------------------------------

def list_tables(conn) -> list[str]:
    rows = query(
        conn,
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;",
    )
    return [r["tablename"] for r in rows]


def table_columns(conn, table: str) -> list[dict[str, Any]]:
    return query(
        conn,
        """
        SELECT column_name, data_type, udt_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position;
        """,
        (table,),
    )


def table_count(conn, table: str) -> int:
    rows = query(conn, f"SELECT COUNT(*) AS c FROM {quote_ident(table)};")
    return int(rows[0]["c"])


def table_size_pretty(conn, table: str) -> str:
    rows = query(conn, "SELECT pg_size_pretty(pg_total_relation_size(%s)) AS s;", (f"public.{table}",))
    return rows[0]["s"] if rows else "-"
