"""
Создание ссылки события (INSERT в event_links).

Поля: event_id (FK), type (enum link_type), url (CHECK ^https?://), title, sort_order.

Запуск:  python events/create_event-link.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

LINK_TYPES = ("ticket_sale", "website", "social", "stream", "other")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Создание ссылки события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0

        _, ltype = crud.ask_enum("type", LINK_TYPES, current="website")
        url = ui.ask("url (http(s)://...)").strip()
        if not url.startswith(("http://", "https://")):
            print(ui.fail("  url должен начинаться с http:// или https://"))
            return 0
        title = ui.ask("title (Enter — пусто)", default="").strip() or None
        sort_order = ui.ask_int("sort_order", default=0) or 0

        data = {"event_id": eid, "type": ltype, "url": url, "title": title, "sort_order": sort_order}
        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать ссылку?"):
            print(ui.dim("  Отменено."))
            return 0

        nid = crud.run_insert(conn, "event_links", data)
        if nid is not None:
            print(ui.ok(f"  Создана ссылка id={nid}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
