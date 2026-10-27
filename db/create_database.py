"""
Создание чистой схемы БД из файла schema.dbml (или готового .sql).

Если передан .dbml — он конвертируется в PostgreSQL SQL тем же конвертером,
что и service/convert_dbml-to-sql.py. Если передан .sql — выполняется как есть.

Перед запуском БД должна быть пустой. Для полного сброса используйте
db/reset_database.py.

Запуск:
    python db/create_database.py
    python db/create_database.py --file schema.dbml
    python db/create_database.py --file schema.sql
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import db, ui

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "schema.dbml"


def _resolve_source(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _load_sql(source: Path) -> str:
    suffix = source.suffix.lower()
    if suffix == ".sql":
        return source.read_text(encoding="utf-8")

    if suffix == ".dbml":
        try:
            from lark_dbml import load
            from lark_dbml.converter import to_sql
            from sqlglot import Dialects
        except ImportError as e:
            raise RuntimeError(
                "Для конвертации schema.dbml нужны lark-dbml и sqlglot. "
                "Установите зависимости из requirements.txt."
            ) from e

        diagram = load(str(source))
        body = to_sql(diagram, Dialects.POSTGRES)
        return (
            "-- Auto-generated from DBML\n"
            "CREATE EXTENSION IF NOT EXISTS citext;\n\n"
            f"{body}\n"
        )

    raise RuntimeError(
        f"Неподдерживаемый формат файла: {source.name}. Ожидается .dbml или .sql."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Создать схему БД из schema.dbml или готового SQL-файла."
    )
    parser.add_argument(
        "--file",
        default=str(DEFAULT_SOURCE),
        help="Путь к .dbml или .sql (по умолчанию schema.dbml в корне проекта).",
    )
    args = parser.parse_args()

    source = _resolve_source(args.file)
    if not source.exists():
        print(ui.fail(f"Файл не найден: {source}"))
        return 1

    try:
        sql = _load_sql(source)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подготовить SQL: {e}"))
        return 1

    if not sql.strip():
        print(ui.fail("Подготовленный SQL пуст."))
        return 1

    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1

    try:
        ui.header("СОЗДАНИЕ СХЕМЫ БД")
        print(f"  источник: {source}")
        print(f"  размер SQL: {len(sql):,} символов".replace(",", " "))
        print(ui.warn("  База должна быть пустой. Иначе создание завершится ошибкой."))

        if not ui.confirm("Создать схему из указанного файла?"):
            print(ui.dim("  Отменено."))
            return 0

        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            print(ui.fail(f"  Ошибка создания схемы: {e}"))
            print(ui.warn("  Изменения откатаны. Для чистого старта используйте db/reset_database.py."))
            return 1

        try:
            tables = db.list_tables(conn)
            print(ui.ok(f"  Схема создана. Таблиц в public: {len(tables)}"))
        except Exception:  # noqa: BLE001
            print(ui.ok("  Схема создана."))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
