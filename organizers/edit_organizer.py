"""
Редактирование организатора (UPDATE organizers).

Запуск:  python organizers/edit_organizer.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

LEGAL_FORMS = ("individual", "legal_entity")
STATUSES = ("draft", "active", "suspended", "archived")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Редактирование организатора")
        oid = crud.pick_id(conn, "organizers")
        if oid is None:
            return 0
        o = crud.fetch_one(conn, "organizers", oid)
        ui.print_table(["поле", "значение"],
                       [["slug", o["slug"]], ["name", o["name"]], ["status", o["status"]],
                        ["legal_form", o["legal_form"]], ["inn", o["inn"]], ["ogrn", o["ogrn"]],
                        ["avatar_media_id", o["avatar_media_id"]], ["cover_media_id", o["cover_media_id"]]],
                       max_width=60)
        updates: dict = {}

        ch, val = crud.ask_text("slug", o["slug"])
        if ch and val:
            updates["slug"] = val
        ch, val = crud.ask_text("name", o["name"])
        if ch and val:
            updates["name"] = val
        ch, val = crud.ask_text("short_description", o["short_description"])
        if ch:
            updates["short_description"] = val
        ch, val = crud.ask_text("description", o["description"])
        if ch:
            updates["description"] = val
        ch, val = crud.ask_fk(conn, "avatar_media_id", "media", current=o["avatar_media_id"], label_cols=("storage_key",))
        if ch:
            updates["avatar_media_id"] = val
        ch, val = crud.ask_fk(conn, "cover_media_id", "media", current=o["cover_media_id"], label_cols=("storage_key",))
        if ch:
            updates["cover_media_id"] = val
        ch, val = crud.ask_enum("legal_form", LEGAL_FORMS, current=o["legal_form"])
        if ch:
            updates["legal_form"] = val
        ch, val = crud.ask_text("inn", o["inn"])
        if ch:
            updates["inn"] = val
        ch, val = crud.ask_text("ogrn", o["ogrn"])
        if ch:
            updates["ogrn"] = val
        ch, val = crud.ask_enum("status", STATUSES, current=o["status"])
        if ch:
            updates["status"] = val

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        ui.section("Изменения")
        crud.show_diff(updates, before=o)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0

        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if v == 'now()' else '%s'}" for k, v in updates.items()
        )
        params = [v for k, v in updates.items() if v != "now()"] + [oid]
        try:
            db.execute(conn, f"UPDATE organizers SET {set_clause} WHERE id=%s;", params)
            print(ui.ok("  Обновлено."))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
