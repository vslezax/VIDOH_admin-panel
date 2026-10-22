"""
Редактирование позиции заказа (UPDATE order_items).

Запуск:  python sales/edit_order-item.py
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
        ui.header("Редактирование позиции заказа")
        oid = crud.pick_id(conn, "orders")
        if oid is None:
            return 0
        rows = db.query(conn, "SELECT * FROM order_items WHERE order_id=%s ORDER BY id;", (oid,))
        crud.print_rows(rows, ["id", "ticket_id", "quantity", "unit_price", "total_price"], max_width=30)
        if not rows:
            return 0
        iid = ui.ask_int("ID позиции")
        if iid is None:
            return 0
        it = next((r for r in rows if r["id"] == iid), None)
        if not it:
            print(ui.fail("  Позиция не найдена у этого заказа."))
            return 0

        updates: dict = {}
        ch, val = crud.ask_fk(conn, "ticket_id", "tickets", current=it["ticket_id"], label_cols=("name",), allow_null=False)
        if ch and val is not None:
            updates["ticket_id"] = val
        ch, val = crud.ask_int("quantity", it["quantity"], min_value=1)
        if ch and val is not None:
            updates["quantity"] = val
        ch, val = crud.ask_decimal("unit_price", it["unit_price"])
        if ch and val is not None:
            if val < 0:
                print(ui.warn("  unit_price >= 0 — пропускаю."))
            else:
                updates["unit_price"] = val
        ch, val = crud.ask_decimal("total_price", it["total_price"])
        if ch and val is not None:
            if val < 0:
                print(ui.warn("  total_price >= 0 — пропускаю."))
            else:
                updates["total_price"] = val
        ch, val = crud.ask_text("event_title_snapshot", it["event_title_snapshot"])
        if ch:
            updates["event_title_snapshot"] = val
        ch, val = crud.ask_text("ticket_name_snapshot", it["ticket_name_snapshot"])
        if ch:
            updates["ticket_name_snapshot"] = val

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        crud.show_diff(updates, before=it)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        n = crud.run_update(conn, "order_items", iid, updates)
        print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
