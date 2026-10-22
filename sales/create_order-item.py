"""
Создание позиции заказа (INSERT в order_items).

Обязательные: order_id (FK), ticket_id (FK), quantity > 0,
unit_price >= 0, total_price >= 0. Снапшоты названий — опционально.

Запуск:  python sales/create_order-item.py
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
        ui.header("Создание позиции заказа")
        _, order_id = crud.ask_fk(conn, "order_id", "orders", label_cols=("status",), allow_null=False)
        if order_id is None:
            return 0
        data: dict = {"order_id": order_id}
        _, ticket_id = crud.ask_fk(conn, "ticket_id", "tickets", label_cols=("name",), allow_null=False)
        if ticket_id is None:
            return 0
        data["ticket_id"] = ticket_id

        ch, qty = crud.ask_int("quantity", required=True, min_value=1)
        data["quantity"] = qty
        ch, unit = crud.ask_decimal("unit_price", required=True)
        if unit is None or unit < 0:
            print(ui.fail("  unit_price >= 0 (CHECK)."))
            return 0
        data["unit_price"] = unit
        ch, total = crud.ask_decimal("total_price", required=True)
        if total is None or total < 0:
            print(ui.fail("  total_price >= 0 (CHECK)."))
            return 0
        data["total_price"] = total
        ch, val = crud.ask_text("event_title_snapshot")
        if ch and val:
            data["event_title_snapshot"] = val
        ch, val = crud.ask_text("ticket_name_snapshot")
        if ch and val:
            data["ticket_name_snapshot"] = val

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать позицию?"):
            print(ui.dim("  Отменено."))
            return 0
        nid = crud.run_insert(conn, "order_items", data)
        if nid is not None:
            print(ui.ok(f"  Создана позиция id={nid}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
