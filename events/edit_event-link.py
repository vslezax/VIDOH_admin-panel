"""
Редактирование ссылки события (UPDATE event_links).

Запуск:  python events/edit_event-link.py
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
        ui.header("Редактирование ссылки события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        rows = db.query(conn, "SELECT * FROM event_links WHERE event_id=%s ORDER BY id;", (eid,))
        crud.print_rows(rows, ["id", "type", "url", "title", "sort_order"], max_width=50)
        if not rows:
            return 0
        lid = ui.ask_int("ID ссылки для редактирования")
        if lid is None:
            return 0
        link = next((r for r in rows if r["id"] == lid), None)
        if not link:
            print(ui.fail("  Ссылка не найдена у этого события."))
            return 0

        updates: dict = {}
        ch, val = crud.ask_enum("type", LINK_TYPES, current=link["type"])
        if ch:
            updates["type"] = val
        raw = ui.ask(f"url (текущее: {link['url']}), Enter — оставить").strip()
        if raw:
            if not raw.startswith(("http://", "https://")):
                print(ui.warn("  url должен начинаться с http(s):// — пропускаю."))
            else:
                updates["url"] = raw
        ch, val = crud.ask_text("title", link["title"])
        if ch:
            updates["title"] = val
        ch, val = crud.ask_int("sort_order", link["sort_order"])
        if ch and val is not None:
            updates["sort_order"] = val

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        ui.section("Изменения")
        crud.show_diff(updates, before=link)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        n = crud.run_update(conn, "event_links", lid, updates)
        if n:
            print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
