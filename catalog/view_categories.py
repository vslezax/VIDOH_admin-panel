"""
Просмотр категорий (таблица categories).

Запуск:  python catalog/view_categories.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Категории")
        rows = db.query(conn, "SELECT id, slug, name, icon_media_id, sort_order FROM categories ORDER BY sort_order, id;")
        crud.print_rows(rows, max_width=40) if rows else print(ui.dim("  нет"))
        print(ui.ok(f"\n  Всего категорий: {len(rows)}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
