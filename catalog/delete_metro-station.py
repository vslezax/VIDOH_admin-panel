"""
Удаление станции метро (DELETE из metro_stations).

delete_guard покажет зависимость: venues.metro_station_id — SET NULL
(ссылки площадок будут обнулены).

ВНИМАНИЕ: необратимо.

Запуск:  python catalog/delete_metro-station.py
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
        ui.header("Удаление станции метро")
        sid = crud.pick_id(conn, "metro_stations")
        if sid is None:
            return 0
        s = crud.fetch_one(conn, "metro_stations", sid)
        ui.print_table(
            ["поле", "значение"],
            [["id", s["id"]], ["city_id", s["city_id"]], ["name", s["name"]],
             ["line_name", s["line_name"]], ["line_color", s["line_color"]]],
            max_width=60,
        )
        deps = delete_guard.collect_dependencies(conn, "metro_stations", sid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить станцию метро id={sid}?"):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM metro_stations WHERE id=%s;", (sid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
