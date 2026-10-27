"""
Создание станции метро (INSERT в metro_stations).

Обязательные: city_id (FK), name, line_name.
CHECK: line_color IS NULL OR line_color ~ '^#[0-9A-Fa-f]{6}$'; sort_order >= 0.
UNIQUE (city_id, name).

Запуск:  python catalog/create_metro-station.py
"""
from __future__ import annotations

import os
import re
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Создание станции метро")
        _, city_id = crud.ask_fk(conn, "city_id", "cities", label_cols=("name",), allow_null=False)
        if city_id is None:
            return 0
        data: dict = {"city_id": city_id}

        _, name = crud.ask_text("name", required=True)
        if not name:
            print(ui.fail("  name обязателен (NOT NULL)."))
            return 0
        data["name"] = name

        _, line_name = crud.ask_text("line_name", required=True)
        if not line_name:
            print(ui.fail("  line_name обязателен (NOT NULL)."))
            return 0
        data["line_name"] = line_name

        raw_color = ui.ask("line_color (#RRGGBB, Enter — пусто)", default="").strip()
        if raw_color:
            if not _COLOR_RE.match(raw_color):
                print(ui.fail("  line_color должен быть в формате #RRGGBB (CHECK)."))
                return 0
            data["line_color"] = raw_color

        ch, icon_id = crud.ask_fk(conn, "line_icon_media_id", "media", label_cols=("storage_key",))
        if ch and icon_id is not None:
            mtype = db.query(conn, "SELECT type FROM media WHERE id=%s;", (icon_id,))
            if not mtype or mtype[0]["type"] != "image":
                print(ui.fail("  line_icon_media_id должен ссылаться на media.type='image'."))
                return 0
            data["line_icon_media_id"] = icon_id

        sort_order = ui.ask_int("sort_order", default=0) or 0
        if sort_order < 0:
            print(ui.fail("  sort_order должен быть >= 0 (CHECK)."))
            return 0
        data["sort_order"] = sort_order

        dup = db.query(
            conn,
            "SELECT 1 FROM metro_stations WHERE city_id=%s AND name=%s;",
            (city_id, name),
        )
        if dup:
            print(ui.warn("  Станция с таким name уже есть в этом городе (UNIQUE city_id, name)."))
            return 0

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать станцию метро?"):
            print(ui.dim("  Отменено."))
            return 0

        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO metro_stations ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создана станция метро id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
