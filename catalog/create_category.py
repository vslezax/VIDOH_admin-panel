"""
Создание категории (INSERT в categories).

Обязательные: slug (уникальный), name.

Запуск:  python catalog/create_category.py
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
        ui.header("Создание категории")
        data: dict = {}
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
        ch, val = crud.ask_text("description")
        if ch and val:
            data["description"] = val
        ch, val = crud.ask_fk(conn, "icon_media_id", "media", label_cols=("storage_key",))
        if ch and val is not None:
            data["icon_media_id"] = val
        sort_order = ui.ask_int("sort_order", default=0) or 0
        data["sort_order"] = sort_order

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать категорию?"):
            print(ui.dim("  Отменено."))
            return 0
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO categories ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создана категория id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
