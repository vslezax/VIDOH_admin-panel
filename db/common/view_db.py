"""
Просмотр базы данных VIDOH.

Интерактивный консольный скрипт для чтения структуры и данных БД:
  - сводка по всем таблицам (имя, количество строк, размер);
  - список таблиц с колонками, типами, NULL-флагами;
  - просмотр содержимого таблицы с пагинацией и сортировкой;
  - быстрый поиск по текстовым колонкам.

Только чтение — никаких изменений не вносит.

Запуск:  python view_db.py
"""
from __future__ import annotations

import os
import sys
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r'..\..'))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import sys

from lib import db, ui


# Человекочитаемые названия внутренних типов PostgreSQL
_TYPE_NAMES = {
    "int8": "bigint",
    "int4": "integer",
    "int2": "smallint",
    "bpchar": "char",
    "bool": "boolean",
    "float8": "double",
    "float4": "real",
}


def _type_name(col: dict) -> str:
    """Возвращает понятный тип; enum-имена и прочее оставляем как есть."""
    udt = col["udt_name"]
    return _TYPE_NAMES.get(udt, udt)


def show_overview(conn) -> None:
    ui.header("Сводка по таблицам (схема public)")
    tables = db.list_tables(conn)
    if not tables:
        print(ui.fail("  Таблиц нет. Сначала разверните схему."))
        return

    rows = []
    total_rows = 0
    for t in tables:
        try:
            cnt = db.table_count(conn, t)
        except Exception as e:  # noqa: BLE001
            rows.append([t, "ERR", "-", str(e)[:40]])
            continue
        total_rows += cnt
        rows.append([t, f"{cnt:,}".replace(",", " "), db.table_size_pretty(conn, t)])

    ui.print_table(["таблица", "строк", "размер"], rows, max_width=30)
    print(ui.ok(f"\n  Всего таблиц: {len(tables)}, строк суммарно: {total_rows:,}".replace(",", " ")))


def show_structure(conn) -> None:
    ui.header("Структура таблиц")
    tables = db.list_tables(conn)
    for t in tables:
        cols = db.table_columns(conn, t)
        ui.section(t)
        rows = []
        for c in cols:
            nn = "" if c["is_nullable"] == "YES" else "NOT NULL"
            default = c["column_default"] or ""
            rows.append([c["column_name"], _type_name(c), nn, default])
        ui.print_table(["колонка", "тип", "constraint", "default"], rows, max_width=35)


def _order_clause(conn, table: str) -> str:
    """Пытается сортировать по id, иначе по первой колонке."""
    cols = [c["column_name"] for c in db.table_columns(conn, table)]
    if "id" in cols:
        return f"ORDER BY {db.quote_ident('id')}"
    return ""


def browse_table(conn) -> None:
    ui.header("Просмотр содержимого таблицы")
    tables = db.list_tables(conn)
    if not tables:
        print(ui.fail("  Таблиц нет."))
        return

    print("  Доступные таблицы:")
    for i, t in enumerate(tables, 1):
        print(f"    {i:2}. {t}")

    choice = ui.ask("Название таблицы (или номер)")
    if not choice:
        return
    if choice.isdigit() and 1 <= int(choice) <= len(tables):
        table = tables[int(choice) - 1]
    else:
        table = choice
    if table not in tables:
        print(ui.fail(f"  Таблица '{table}' не найдена."))
        return

    limit = ui.ask_int("Сколько строк показать", default=20) or 20
    offset = 0
    order = _order_clause(conn, table)

    while True:
        sql = f"SELECT * FROM {db.quote_ident(table)} {order} LIMIT %s OFFSET %s;"
        rows = db.query(conn, sql, (limit, offset))
        total = db.table_count(conn, table)

        ui.section(f"{table}  (строки {offset + 1}–{offset + len(rows)} из {total})")
        if rows:
            columns = list(rows[0].keys())
            ui.print_table(columns, [list(r.values()) for r in rows], max_width=30)
        else:
            print(ui.dim("  (нет данных)"))

        print()
        print("  [n] следующая страница   [p] предыдущая   [q] выход")
        nav = ui.ask("Действие", default="q").lower()
        if nav == "n":
            if offset + limit < total:
                offset += limit
            else:
                print(ui.dim("  Это последняя страница."))
        elif nav == "p":
            offset = max(0, offset - limit)
        else:
            break


def search_table(conn) -> None:
    """Простой поиск: ILIKE по всем текстовым колонкам таблицы."""
    ui.header("Поиск по таблице")
    tables = db.list_tables(conn)
    table = ui.ask("Название таблицы")
    if table not in tables:
        print(ui.fail(f"  Таблица '{table}' не найдена."))
        return
    term = ui.ask("Что искать")
    if not term:
        return

    text_cols = [
        c["column_name"]
        for c in db.table_columns(conn, table)
        if c["udt_name"] in ("varchar", "text", "citext", "bpchar", "char", "name")
    ]
    if not text_cols:
        print(ui.warn("  В таблице нет текстовых колонок для поиска."))
        return

    cond = " OR ".join(f"{db.quote_ident(c)}::text ILIKE %s" for c in text_cols)
    sql = f"SELECT * FROM {db.quote_ident(table)} WHERE {cond} LIMIT 50;"
    rows = db.query(conn, sql, tuple([f"%{term}%"] * len(text_cols)))
    ui.section(f"Найдено: {len(rows)}")
    if rows:
        columns = list(rows[0].keys())
        ui.print_table(columns, [list(r.values()) for r in rows], max_width=30)
    else:
        print(ui.dim("  Ничего не найдено."))


ACTIONS = {
    "1": ("Сводка по таблицам", show_overview),
    "2": ("Структура таблиц", show_structure),
    "3": ("Просмотр таблицы", browse_table),
    "4": ("Поиск по таблице", search_table),
}


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1

    try:
        while True:
            choice = ui.menu(
                "VIEW DB — просмотр базы данных",
                [(k, label) for k, (label, _) in ACTIONS.items()],
            )
            if choice is None:
                print(ui.dim("Пока."))
                break
            if choice in ACTIONS:
                try:
                    ACTIONS[choice][1](conn)
                except Exception as e:  # noqa: BLE001
                    print(ui.fail(f"Ошибка: {e}"))
            else:
                print(ui.warn("Нет такого пункта."))
            ui.pause()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())