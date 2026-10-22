"""
Удаление организатора (DELETE из organizers).

delete_guard покажет зависимости:
  - CASCADE: organizer_contacts, event_organizers — БУДУТ УДАЛЕНЫ;
  - SET NULL / NO ACTION: по ситуации.
ВНИМАНИЕ: необратимо.

Запуск:  python organizers/delete_organizer.py
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
        ui.header("Удаление организатора")
        oid = crud.pick_id(conn, "organizers")
        if oid is None:
            return 0
        o = crud.fetch_one(conn, "organizers", oid)
        ui.section("Карточка организатора")
        ui.print_table(["поле", "значение"],
                       [["id", o["id"]], ["slug", o["slug"]], ["name", o["name"]], ["status", o["status"]]],
                       max_width=60)

        ui.section("Проверка зависимых записей")
        deps = delete_guard.collect_dependencies(conn, "organizers", oid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить организатора id={oid}? Связанные данные будут затронуты."):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM organizers WHERE id=%s;", (oid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка удаления: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
