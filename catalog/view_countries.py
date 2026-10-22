"""
Просмотр стран (таблица countries).

Запуск:  python catalog/view_countries.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import db, ui


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Страны")
        rows = db.query(conn, "SELECT id, name, iso FROM countries ORDER BY name;")
        ui.print_table(["id", "name", "iso"], [[r["id"], r["name"], r["iso"]] for r in rows], max_width=40)
        print(ui.ok(f"\n  Всего стран: {len(rows)}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
