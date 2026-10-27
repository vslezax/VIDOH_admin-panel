"""
ПОЛНЫЙ сброс базы данных: удаление всех пользовательских схем, таблиц,
данных, ключей, типов, последовательностей и индексов.

Скрипт удаляет все несистемные схемы (включая public) и создаёт public заново.
Сама база и роль подключения остаются.

ВНИМАНИЕ: операция необратима. Для подтверждения нужно ввести RESET.

Запуск:  python db/reset_database.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import db, ui


def _list_user_schemas(cur) -> list[str]:
    cur.execute(
        """
        SELECT nspname
        FROM pg_namespace
        WHERE nspname NOT LIKE 'pg_%'
          AND nspname <> 'information_schema'
        ORDER BY nspname;
        """
    )
    return [row[0] for row in cur.fetchall()]


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1

    try:
        with conn.cursor() as cur:
            schemas = _list_user_schemas(cur)

        ui.header("ПОЛНЫЙ СБРОС БАЗЫ ДАННЫХ")
        print(ui.warn("  Будут удалены ВСЕ пользовательские схемы, таблицы, данные,"))
        print(ui.warn("  ключи, типы, индексы и последовательности."))
        ui.section("Схемы к удалению")
        if schemas:
            for name in schemas:
                print(f"    - {name}")
        else:
            print(ui.dim("    (пользовательских схем нет)"))

        answer = ui.ask("Введите RESET для подтверждения").strip()
        if answer != "RESET":
            print(ui.dim("  Отменено."))
            return 0

        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                for name in schemas:
                    cur.execute(f"DROP SCHEMA IF EXISTS {db.quote_ident(name)} CASCADE;")
                cur.execute("CREATE SCHEMA IF NOT EXISTS public;")
                cur.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER;")
                cur.execute("GRANT ALL ON SCHEMA public TO public;")
            conn.commit()
            print(ui.ok("  База данных полностью очищена. Схема public создана заново."))
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            print(ui.fail(f"  Ошибка сброса: {e}"))
            return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
