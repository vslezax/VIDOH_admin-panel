"""
Редактирование города (UPDATE cities).

Запуск:  python catalog/edit_city.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

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
        ui.header("Редактирование города")
        cid = crud.pick_id(conn, "cities")
        if cid is None:
            return 0
        c = crud.fetch_one(conn, "cities", cid)
        ui.print_table(["поле", "значение"],
                       [["name", c["name"]], ["slug", c["slug"]], ["country_id", c["country_id"]],
                        ["lat", c["lat"]], ["lng", c["lng"]], ["timezone", c["timezone"]]], max_width=60)
        updates: dict = {}
        ch, val = crud.ask_fk(conn, "country_id", "countries", current=c["country_id"], label_cols=("name", "iso"), allow_null=False)
        if ch and val is not None:
            updates["country_id"] = val
        ch, val = crud.ask_text("name", c["name"])
        if ch and val:
            updates["name"] = val
        ch, val = crud.ask_text("slug", c["slug"])
        if ch and val:
            updates["slug"] = val
        raw = ui.ask(f"lat (текущее: {c['lat']}), Enter — оставить").strip()
        if raw:
            try:
                lat = float(raw.replace(",", "."))
                if -90 <= lat <= 90:
                    updates["lat"] = lat
                else:
                    print(ui.warn("  lat вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lat не число — пропускаю."))
        raw = ui.ask(f"lng (текущее: {c['lng']}), Enter — оставить").strip()
        if raw:
            try:
                lng = float(raw.replace(",", "."))
                if -180 <= lng <= 180:
                    updates["lng"] = lng
                else:
                    print(ui.warn("  lng вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lng не число — пропускаю."))
        ch, val = crud.ask_text("timezone", c["timezone"])
        if ch and val:
            updates["timezone"] = val

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        crud.show_diff(updates, before=c)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        updates["updated_at"] = datetime.now()
        n = crud.run_update(conn, "cities", cid, updates)
        print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
