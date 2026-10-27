"""
Редактирование станции метро (UPDATE metro_stations).

Запуск:  python catalog/edit_metro-station.py
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime

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
        ui.header("Редактирование станции метро")
        sid = crud.pick_id(conn, "metro_stations")
        if sid is None:
            return 0
        s = crud.fetch_one(conn, "metro_stations", sid)
        ui.print_table(
            ["поле", "значение"],
            [["city_id", s["city_id"]], ["name", s["name"]], ["line_name", s["line_name"]],
             ["line_color", s["line_color"]], ["line_icon_media_id", s["line_icon_media_id"]],
             ["sort_order", s["sort_order"]]],
            max_width=60,
        )
        updates: dict = {}

        ch, val = crud.ask_fk(conn, "city_id", "cities", current=s["city_id"], label_cols=("name",), allow_null=False)
        if ch and val is not None:
            updates["city_id"] = val
        ch, val = crud.ask_text("name", s["name"])
        if ch:
            if not val:
                print(ui.warn("  name не может быть NULL (NOT NULL) — пропускаю."))
            else:
                updates["name"] = val
        ch, val = crud.ask_text("line_name", s["line_name"])
        if ch:
            if not val:
                print(ui.warn("  line_name не может быть NULL (NOT NULL) — пропускаю."))
            else:
                updates["line_name"] = val

        raw_color = ui.ask(f"line_color (текущее: {s['line_color'] or 'пусто'}), Enter — оставить, 'null' — очистить").strip()
        if raw_color:
            if raw_color.lower() in crud.NULL_TOKENS:
                updates["line_color"] = None
            elif not _COLOR_RE.match(raw_color):
                print(ui.fail("  line_color должен быть в формате #RRGGBB (CHECK)."))
                return 0
            else:
                updates["line_color"] = raw_color

        ch, val = crud.ask_fk(conn, "line_icon_media_id", "media", current=s["line_icon_media_id"], label_cols=("storage_key",))
        if ch:
            if val is not None:
                mtype = db.query(conn, "SELECT type FROM media WHERE id=%s;", (val,))
                if not mtype or mtype[0]["type"] != "image":
                    print(ui.fail("  line_icon_media_id должен ссылаться на media.type='image'."))
                    return 0
            updates["line_icon_media_id"] = val

        ch, val = crud.ask_int("sort_order", s["sort_order"], min_value=0)
        if ch and val is not None:
            updates["sort_order"] = val

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0

        new_city = updates.get("city_id", s["city_id"])
        new_name = updates.get("name", s["name"])
        dup = db.query(
            conn,
            "SELECT 1 FROM metro_stations WHERE city_id=%s AND name=%s AND id<>%s;",
            (new_city, new_name, sid),
        )
        if dup:
            print(ui.warn("  Станция с таким name уже есть в этом городе (UNIQUE city_id, name)."))
            return 0

        ui.section("Изменения")
        crud.show_diff(updates, before=s)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0

        updates["updated_at"] = datetime.now()
        n = crud.run_update(conn, "metro_stations", sid, updates)
        print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
