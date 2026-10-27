"""
Создание организатора (INSERT в organizers).

Обязательные: slug, name. legal_form/status имеют DEFAULT.
Медиа (avatar/cover) — FK на media (проверяются).

Запуск:  python organizers/create_organizer.py
"""
from __future__ import annotations

import os
import sys
import uuid

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
        ui.header("Создание организатора")
        data: dict = {"uuid": str(uuid.uuid4())}

        _, slug = crud.ask_text("slug", required=True)
        if not slug:
            print(ui.warn("  slug обязателен."))
            return 0
        data["slug"] = slug
        _, name = crud.ask_text("name", required=True)
        if not name:
            print(ui.warn("  name обязателен."))
            return 0
        data["name"] = name

        ch, val = crud.ask_text("short_description")
        if ch and val:
            data["short_description"] = val
        ch, val = crud.ask_text("description")
        if ch and val:
            data["description"] = val

        ch, val = crud.ask_fk(conn, "avatar_media_id", "media", label_cols=("storage_key",))
        if ch and val is not None:
            data["avatar_media_id"] = val
        ch, val = crud.ask_fk(conn, "cover_media_id", "media", label_cols=("storage_key",))
        if ch and val is not None:
            data["cover_media_id"] = val

        _, lf = crud.ask_enum("legal_form", LEGAL_FORMS, current="legal_entity")
        data["legal_form"] = lf
        ch, val = crud.ask_text("inn")
        if ch and val:
            data["inn"] = val
        ch, val = crud.ask_text("ogrn")
        if ch and val:
            data["ogrn"] = val
        if lf == "legal_entity":
            inn = data.get("inn")
            ogrn = data.get("ogrn")
            if not inn or len(inn) not in (10, 12):
                print(ui.fail("  Для legal_entity нужен inn длиной 10 или 12 символов (CHECK)."))
                return 0
            if not ogrn or len(ogrn) not in (13, 15):
                print(ui.fail("  Для legal_entity нужен ogrn длиной 13 или 15 символов (CHECK)."))
                return 0
        _, status = crud.ask_enum("status", STATUSES, current="draft")
        data["status"] = status

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать организатора?"):
            print(ui.dim("  Отменено."))
            return 0

        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO organizers ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан организатор id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
