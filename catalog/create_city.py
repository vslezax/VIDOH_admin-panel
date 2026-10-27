"""
Создание города (INSERT в cities).

Обязательные: country_id (FK), name, slug. UNIQUE(country_id, slug).
CHECK: lat между -90..90, lng между -180..180.

Запуск:  python catalog/create_city.py
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
        ui.header("Создание города")
        _, country_id = crud.ask_fk(conn, "country_id", "countries", label_cols=("name", "iso"), allow_null=False)
        if country_id is None:
            return 0
        data: dict = {"country_id": country_id}
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

        raw_lat = ui.ask("lat (-90..90, Enter — пусто)").strip()
        if raw_lat:
            try:
                lat = float(raw_lat.replace(",", "."))
                if -90 <= lat <= 90:
                    data["lat"] = lat
                else:
                    print(ui.warn("  lat вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lat не число — пропускаю."))
        raw_lng = ui.ask("lng (-180..180, Enter — пусто)").strip()
        if raw_lng:
            try:
                lng = float(raw_lng.replace(",", "."))
                if -180 <= lng <= 180:
                    data["lng"] = lng
                else:
                    print(ui.warn("  lng вне диапазона — пропускаю."))
            except ValueError:
                print(ui.warn("  lng не число — пропускаю."))
        tz = ui.ask("timezone", default="UTC").strip() or "UTC"
        data["timezone"] = tz

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать город?"):
            print(ui.dim("  Отменено."))
            return 0
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO cities ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан город id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
