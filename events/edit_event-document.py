"""
Редактирование документа события (UPDATE event_documents).

Запуск:  python events/edit_event-document.py
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
        ui.header("Редактирование документа события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        rows = db.query(conn, "SELECT * FROM event_documents WHERE event_id=%s ORDER BY id;", (eid,))
        crud.print_rows(rows, ["id", "type", "title", "url", "sort_order"], max_width=40)
        if not rows:
            return 0
        did = ui.ask_int("ID документа")
        if did is None:
            return 0
        doc = next((r for r in rows if r["id"] == did), None)
        if not doc:
            print(ui.fail("  Документ не найден у этого события."))
            return 0

        updates: dict = {}
        ch, val = crud.ask_enum("type", DOC_TYPES, current=doc["type"])
        if ch:
            updates["type"] = val
        ch, val = crud.ask_text("title", doc["title"])
        if ch and val:
            updates["title"] = val
        ch, val = crud.ask_text("content", doc["content"])
        if ch:
            updates["content"] = val
        ch, val = crud.ask_text("url", doc["url"])
        if ch:
            updates["url"] = val
        ch, val = crud.ask_int("sort_order", doc["sort_order"])
        if ch and val is not None:
            updates["sort_order"] = val

        # Проверка content OR url
        new_content = updates.get("content", doc["content"])
        new_url = updates.get("url", doc["url"])
        if not new_content and not new_url:
            print(ui.fail("  content и url не могут быть пустыми одновременно (CHECK)."))
            return 0

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        ui.section("Изменения")
        crud.show_diff(updates, before=doc)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0

        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if v == 'now()' else '%s'}" for k, v in updates.items()
        )
        params = [v for k, v in updates.items() if v != "now()"] + [did]
        try:
            db.execute(conn, f"UPDATE event_documents SET {set_clause} WHERE id=%s;", params)
            print(ui.ok("  Обновлено."))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
