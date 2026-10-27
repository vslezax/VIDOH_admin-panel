"""
Редактирование типа билета (UPDATE tickets).

Запуск:  python tickets/edit_ticket.py
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
        ui.header("Редактирование типа билета")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        rows = db.query(conn, "SELECT * FROM tickets WHERE event_id=%s ORDER BY sort_order, id;", (eid,))
        crud.print_rows(rows, ["id", "name", "price", "tickets_count", "sold_count"], max_width=30)
        if not rows:
            return 0
        tid = ui.ask_int("ID билета")
        if tid is None:
            return 0
        t = next((r for r in rows if r["id"] == tid), None)
        if not t:
            print(ui.fail("  Билет не найден у этого события."))
            return 0

        updates: dict = {}
        ch, val = crud.ask_text("name", t["name"])
        if ch and val:
            updates["name"] = val
        ch, val = crud.ask_text("description", t["description"])
        if ch:
            updates["description"] = val
        ch, val = crud.ask_decimal("price", t["price"])
        if ch and val is not None:
            if val < 0:
                print(ui.warn("  price >= 0 (CHECK) — пропускаю."))
            else:
                updates["price"] = val
        raw = ui.ask(f"currency (текущее: {t['currency']}), Enter — оставить").strip().upper()
        if raw:
            if len(raw) != 3:
                print(ui.warn("  currency должен быть ровно 3 символа (CHAR(3)) — пропускаю."))
            else:
                updates["currency"] = raw
        ch, val = crud.ask_int("tickets_count", t["tickets_count"], min_value=1)
        if ch:
            updates["tickets_count"] = val
        ch, val = crud.ask_int("sold_count", t["sold_count"], min_value=0)
        if ch and val is not None:
            updates["sold_count"] = val
        ch, val = crud.ask_text("external_url", t["external_url"])
        if ch:
            updates["external_url"] = val
        ch, val = crud.ask_int("sort_order", t["sort_order"])
        if ch and val is not None:
            updates["sort_order"] = val

        new_cnt = updates.get("tickets_count", t["tickets_count"])
        new_sold = updates.get("sold_count", t["sold_count"])
        if new_cnt is not None and new_sold > new_cnt:
            print(ui.fail("  sold_count не может быть больше tickets_count (CHECK)."))
            return 0

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        crud.show_diff(updates, before=t)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if x == 'now()' else '%s'}" for k, x in updates.items()
        )
        params = [x for x in updates.values() if x != "now()"] + [tid]
        db.execute(conn, f"UPDATE tickets SET {set_clause} WHERE id=%s;", params)
        print(ui.ok("  Обновлено."))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
