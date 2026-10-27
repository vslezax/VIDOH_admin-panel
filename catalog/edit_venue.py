"""
Редактирование площадки (UPDATE venues).

Запуск:  python catalog/edit_venue.py
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
        ui.header("Редактирование площадки")
        vid = crud.pick_id(conn, "venues")
        if vid is None:
            return 0
        v = crud.fetch_one(conn, "venues", vid)
        ui.print_table(["поле", "значение"],
                       [["name", v["name"]], ["slug", v["slug"]], ["city_id", v["city_id"]],
                        ["address", v["address"]], ["metro_station_id", v["metro_station_id"]],
                        ["capacity", v["capacity"]]],
                       max_width=60)
        updates: dict = {}
        ch, val = crud.ask_fk(conn, "city_id", "cities", current=v["city_id"], label_cols=("name",), allow_null=False)
        if ch and val is not None:
            updates["city_id"] = val
        ch, val = crud.ask_text("name", v["name"])
        if ch and val:
            updates["name"] = val
        ch, val = crud.ask_text("slug", v["slug"])
        if ch and val:
            updates["slug"] = val
        ch, val = crud.ask_text("address", v["address"])
        if ch and val:
            updates["address"] = val
        ch, val = crud.ask_fk(conn, "metro_station_id", "metro_stations", current=v["metro_station_id"], label_cols=("name", "line_name"))
        if ch:
            updates["metro_station_id"] = val
        raw = ui.ask(f"lat (текущее: {v['lat']}), Enter — оставить").strip()
        if raw:
            try:
                lat = float(raw.replace(",", "."))
                if -90 <= lat <= 90:
                    updates["lat"] = lat
                else:
                    print(ui.warn("  lat вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lat не число — пропускаю."))
        raw = ui.ask(f"lng (текущее: {v['lng']}), Enter — оставить").strip()
        if raw:
            try:
                lng = float(raw.replace(",", "."))
                if -180 <= lng <= 180:
                    updates["lng"] = lng
                else:
                    print(ui.warn("  lng вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lng не число — пропускаю."))
        ch, val = crud.ask_int("capacity", v["capacity"], min_value=1)
        if ch:
            updates["capacity"] = val
        new_lat = updates.get("lat", v["lat"])
        new_lng = updates.get("lng", v["lng"])
        if (new_lat is None) != (new_lng is None):
            print(ui.fail("  lat и lng нужно задать парой (CHECK)."))
            return 0

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        crud.show_diff(updates, before=v)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if x == 'now()' else '%s'}" for k, x in updates.items()
        )
        params = [x for x in updates.values() if x != "now()"] + [vid]
        db.execute(conn, f"UPDATE venues SET {set_clause} WHERE id=%s;", params)
        print(ui.ok("  Обновлено."))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
