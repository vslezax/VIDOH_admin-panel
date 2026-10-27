"""
Редактирование заказа (UPDATE orders).

Запуск:  python sales/edit_order.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("pending", "paid", "cancelled", "refunded", "failed")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Редактирование заказа")
        oid = crud.pick_id(conn, "orders")
        if oid is None:
            return 0
        o = crud.fetch_one(conn, "orders", oid)
        ui.print_table(["поле", "значение"],
                       [["user_id", o["user_id"]], ["event_id", o["event_id"]], ["status", o["status"]],
                        ["total_amount", o["total_amount"]], ["currency", o["currency"]],
                        ["promo_code_id", o["promo_code_id"]], ["paid_at", o["paid_at"]],
                        ["cancelled_at", o["cancelled_at"]]], max_width=60)
        updates: dict = {}

        ch, val = crud.ask_fk(conn, "user_id", "users", current=o["user_id"], label_cols=("email",), allow_null=False)
        if ch and val is not None:
            updates["user_id"] = val
        ch, val = crud.ask_fk(conn, "event_id", "events", current=o["event_id"], label_cols=("title",), allow_null=False)
        if ch and val is not None:
            updates["event_id"] = val
        ch, val = crud.ask_enum("status", STATUSES, current=o["status"])
        if ch:
            updates["status"] = val
        ch, val = crud.ask_decimal("total_amount", o["total_amount"])
        if ch and val is not None:
            if val < 0:
                print(ui.warn("  total_amount >= 0 (CHECK) — пропускаю."))
            else:
                updates["total_amount"] = val
        raw = ui.ask(f"currency (текущее: {o['currency']}), Enter — оставить").strip().upper()
        if raw:
            if len(raw) != 3:
                print(ui.warn("  currency должен быть ровно 3 символа (CHAR(3)) — пропускаю."))
            else:
                updates["currency"] = raw
        ch, val = crud.ask_fk(conn, "promo_code_id", "promo_codes", current=o["promo_code_id"], label_cols=("code",))
        if ch:
            updates["promo_code_id"] = val
        ch, val = crud.ask_datetime("paid_at", o["paid_at"])
        if ch:
            updates["paid_at"] = val
        ch, val = crud.ask_datetime("cancelled_at", o["cancelled_at"])
        if ch:
            updates["cancelled_at"] = val

        new_status = updates.get("status", o["status"])
        new_paid = updates.get("paid_at", o["paid_at"])
        new_cancelled = updates.get("cancelled_at", o["cancelled_at"])
        if new_status == "paid" and not new_paid:
            print(ui.fail("  Для status='paid' нужен paid_at (CHECK)."))
            return 0
        if new_status == "cancelled" and not new_cancelled:
            print(ui.fail("  Для status='cancelled' нужен cancelled_at (CHECK)."))
            return 0

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        crud.show_diff(updates, before=o)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        updates["updated_at"] = datetime.now()
        n = crud.run_update(conn, "orders", oid, updates)
        print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
