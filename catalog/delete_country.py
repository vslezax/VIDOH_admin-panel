"""
Удаление страны (DELETE из countries).

delete_guard покажет зависимости: cities.country_id — NO ACTION (заблокирует,
если есть города страны).

Запуск:  python catalog/delete_country.py
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
        ui.header("Удаление страны")
        cid = crud.pick_id(conn, "countries")
        if cid is None:
            return 0
        c = crud.fetch_one(conn, "countries", cid)
        ui.print_table(["поле", "значение"], [["id", c["id"]], ["name", c["name"]], ["iso", c["iso"]]], max_width=60)
        deps = delete_guard.collect_dependencies(conn, "countries", cid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить страну id={cid}?"):
            print(ui.dim("  Отменено."))
            return 0
        n = db.execute(conn, "DELETE FROM countries WHERE id=%s;", (cid,))
        print(ui.ok(f"  Удалено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
