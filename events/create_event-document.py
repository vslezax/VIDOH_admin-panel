"""
Создание документа события (INSERT в event_documents).

CHECK: content ИЛИ url обязателен.
type — enum document_type.

Запуск:  python events/create_event-document.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

DOC_TYPES = ("service_rules", "payment_rules", "safety_rules", "refund_policy", "other")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Создание документа события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0

        _, dtype = crud.ask_enum("type", DOC_TYPES, current="other")
        title = ui.ask("title").strip()
        if not title:
            print(ui.fail("  title обязателен."))
            return 0

        content = ui.ask("content (Enter — пусто)", default="").strip() or None
        url = ui.ask("url (Enter — пусто)", default="").strip() or None
        if not content and not url:
            print(ui.fail("  Нужно указать content ИЛИ url (CHECK)."))
            return 0
        sort_order = ui.ask_int("sort_order", default=0) or 0

        data = {"event_id": eid, "type": dtype, "title": title,
                "content": content, "url": url, "sort_order": sort_order}
        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать документ?"):
            print(ui.dim("  Отменено."))
            return 0

        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO event_documents ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан документ id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
