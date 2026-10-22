"""
Читает VIDOH.dbml, генерирует schema.sql для PostgreSQL
и добавляет CREATE EXTENSION citext в начало файла.

Пути считаются относительно КОРНЯ проекта (на уровень выше service/).
"""
from pathlib import Path
from lark_dbml import load
from lark_dbml.converter import to_sql
from sqlglot import Dialects

ROOT = Path(__file__).resolve().parent.parent
DBML_FILE = ROOT / "VIDOH.dbml"
SQL_FILE = ROOT / "schema.sql"

def main():
    print(f"[1/3] Читаю {DBML_FILE}...")
    diagram = load(str(DBML_FILE))

    print("[2/3] Генерирую SQL для PostgreSQL...")
    sql = to_sql(diagram, Dialects.POSTGRES)

    # Prepend citext extension, чтобы не падало на типе citext
    header = (
        "-- Auto-generated from DBML\n"
        "CREATE EXTENSION IF NOT EXISTS citext;\n\n"
    )

    Path(SQL_FILE).write_text(header + sql, encoding="utf-8")
    print(f"[3/3] Готово: {SQL_FILE}")


if __name__ == "__main__":
    main()