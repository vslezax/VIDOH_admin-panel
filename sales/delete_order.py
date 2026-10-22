"""
Удаление заказа (DELETE из orders).

delete_guard покажет зависимости:
  - CASCADE: order_items, payments — БУДУТ УДАЛЕНЫ;
  - order_items.ticket_id/issued_tickets — issued_tickets ссылается на order_items
    через NO ACTION, поэтому при наличии выданных билетов удаление заблокируется.
ВНИМАНИЕ: необратимо.

Запуск:  python sales/delete_order.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, delete_guard, ui


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Удаление заказа")
        oid = crud.pick_id(conn, "orders")
        if oid is None:
            return 0
        o = crud.fetch_one(conn, "orders", oid)
        ui.print_table(["поле", "значение"],
                       [["id", o["id"]], ["user_id", o["user_id"]], ["event_id", o["event_id"]],
                        ["status", o["status"]], ["total_amount", o["total_amount"]]], max_width=60)
        deps = delete_guard.collect_dependencies(conn, "orders", oid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить заказ id={oid}? Позиции и платежи удалятся каскадом."):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM orders WHERE id=%s;", (oid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
