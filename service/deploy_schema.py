"""
Подключается к Neon и выполняет schema.sql.
Скрипт идемпотентен: если таблицы уже есть — упадёт с ошибкой,
поэтому сначала используй 3-clear.py, если нужно почистить.
"""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

HERE = Path(__file__).parent
ROOT = HERE.parent
SQL_FILE = ROOT / "schema.sql"


def main():
    load_dotenv(ROOT / ".env")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            f"DATABASE_URL не найден. Проверьте файл {ROOT / '.env'}"
        )

    if not SQL_FILE.exists():
        raise SystemExit(
            f"Файл {SQL_FILE} не найден. Сначала запусти service/convert_dbml-to-sql.py"
        )

    sql = SQL_FILE.read_text(encoding="utf-8")

    print("Подключаюсь к Neon...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        print("Выполняю миграцию...")
        cur.execute(sql)
        print("[SUCCESS] Схема развернута в Neon.")
    except Exception as e:
        print(f"[ERROR] {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()