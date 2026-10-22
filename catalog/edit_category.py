"""
Редактирование категории (UPDATE categories).

Запуск:  python catalog/edit_category.py
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
        ui.header("Редактирование категории")
        cid = crud.pick_id(conn, "categories")
        if cid is None:
            return 0
        c = crud.fetch_one(conn, "categories", cid)
        ui.print_table(["поле", "значение"],
                       [["slug", c["slug"]], ["name", c["name"]], ["icon_media_id", c["icon_media_id"]],
                        ["sort_order", c["sort_order"]]], max_width=60)
        updates: dict = {}
        ch, val = crud.ask_text("slug", c["slug"])
        if ch and val:
            updates["slug"] = val
        ch, val = crud.ask_text("name", c["name"])
        if ch and val:
            updates["name"] = val
        ch, val = crud.ask_text("description", c["description"])
        if ch:
            updates["description"] = val
        ch, val = crud.ask_fk(conn, "icon_media_id", "media", current=c["icon_media_id"], label_cols=("storage_key",))
        if ch:
            updates["icon_media_id"] = val
        ch, val = crud.ask_int("sort_order", c["sort_order"])
        if ch and val is not None:
            updates["sort_order"] = val

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        ui.section("Изменения")
        crud.show_diff(updates, before=c)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if v == 'now()' else '%s'}" for k, v in updates.items()
        )
        params = [v for k, v in updates.items() if v != "now()"] + [cid]
        db.execute(conn, f"UPDATE categories SET {set_clause} WHERE id=%s;", params)
        print(ui.ok("  Обновлено."))
    except Exception as ex:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
