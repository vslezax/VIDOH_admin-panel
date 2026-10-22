"""
Удаляет схему public и создаёт её заново.
Это убирает ВСЕ таблицы, данные, последовательности, представления и т.д.
Сама база и роль остаются.
"""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

WIPE_SQL = """
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;
"""


def main():
    # Явно указываем путь к .env в корне проекта (на уровень выше service/)
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL не задан. Проверьте .env в корне проекта "
            f"({root / '.env'})."
        )

    confirm = input(
        "⚠️  Это удалит ВСЕ таблицы и данные (Y?): "
    ).strip().lower()
    if confirm != "y" and confirm != "Y":
        print("Отменено.")
        return

    print("Подключаюсь к Neon...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        print("Удаляю схему public и создаю заново...")
        cur.execute(WIPE_SQL)
        print("[SUCCESS] База очищена.")
    except Exception as e:
        print(f"[ERROR] {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()