"""
Создание площадки (INSERT в venues).

Обязательные: city_id (FK), slug, name, address. UNIQUE(city_id, slug).
CHECK: lat/lng диапазоны, capacity >= 0.

Запуск:  python catalog/create_venue.py
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
        ui.header("Создание площадки")
        _, city_id = crud.ask_fk(conn, "city_id", "cities", label_cols=("name",), allow_null=False)
        if city_id is None:
            return 0
        data: dict = {"city_id": city_id}
        _, name = crud.ask_text("name", required=True)
        if not name:
            print(ui.warn("  name обязателен."))
            return 0
        data["name"] = name
        _, slug = crud.ask_text("slug", required=True)
        if not slug:
            print(ui.warn("  slug обязателен."))
            return 0
        data["slug"] = slug
        _, address = crud.ask_text("address", required=True)
        if not address:
            print(ui.warn("  address обязателен."))
            return 0
        data["address"] = address

        ch, val = crud.ask_text("metro")
        if ch and val:
            data["metro"] = val
        raw = ui.ask("lat (-90..90, Enter — пусто)").strip()
        if raw:
            try:
                lat = float(raw.replace(",", "."))
                if -90 <= lat <= 90:
                    data["lat"] = lat
                else:
                    print(ui.warn("  lat вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lat не число — пропускаю."))
        raw = ui.ask("lng (-180..180, Enter — пусто)").strip()
        if raw:
            try:
                lng = float(raw.replace(",", "."))
                if -180 <= lng <= 180:
                    data["lng"] = lng
                else:
                    print(ui.warn("  lng вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lng не число — пропускаю."))
        ch, val = crud.ask_int("capacity", min_value=0)
        if ch and val is not None:
            data["capacity"] = val

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать площадку?"):
            print(ui.dim("  Отменено."))
            return 0
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO venues ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создана площадка id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
