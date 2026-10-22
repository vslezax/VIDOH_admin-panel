"""
Удаление категории (DELETE из categories).

delete_guard покажет зависимости: event_categories — CASCADE (привязки удалятся).
ВНИМАНИЕ: необратимо.

Запуск:  python catalog/delete_category.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, delete_guard, ui


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Удаление категории")
        cid = crud.pick_id(conn, "categories")
        if cid is None:
            return 0
        c = crud.fetch_one(conn, "categories", cid)
        ui.section("Карточка категории")
        ui.print_table(["поле", "значение"], [["id", c["id"]], ["slug", c["slug"]], ["name", c["name"]]], max_width=60)
        deps = delete_guard.collect_dependencies(conn, "categories", cid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить категорию id={cid}? Связанные привязки к событиям удалятся."):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM categories WHERE id=%s;", (cid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
