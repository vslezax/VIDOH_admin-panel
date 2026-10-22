"""
Удаление площадки (DELETE из venues).

delete_guard покажет зависимость: events.venue_id — SET NULL
(у событий venue_id обнулится; если у события нет online_url, это может
нарушить CHECK chk_events_venue_or_online — предупреждаем отдельно).

ВНИМАНИЕ: необратимо.

Запуск:  python catalog/delete_venue.py
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
        ui.header("Удаление площадки")
        vid = crud.pick_id(conn, "venues")
        if vid is None:
            return 0
        v = crud.fetch_one(conn, "venues", vid)
        ui.print_table(["поле", "значение"],
                       [["id", v["id"]], ["name", v["name"]], ["slug", v["slug"]], ["address", v["address"]]],
                       max_width=60)

        deps = delete_guard.collect_dependencies(conn, "venues", vid)
        if not delete_guard.report_dependencies(deps):
            return 0

        # Доп. проверка: события без online_url потеряют привязку и нарушат CHECK
        risky = db.query(
            conn,
            "SELECT id, title FROM events WHERE venue_id=%s AND online_url IS NULL;",
            (vid,),
        )
        if risky:
            print(ui.fail("\n  ВНИМАНИЕ: у этих событий venue_id обнулится, а online_url нет —"))
            print(ui.fail("  это нарушит CHECK (venue OR online). Их нужно сначала поправить:"))
            crud.print_rows(risky, max_width=40)

        if not ui.confirm(f"Удалить площадку id={vid}? Операция необратима."):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM venues WHERE id=%s;", (vid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
