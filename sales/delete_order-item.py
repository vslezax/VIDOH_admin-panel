"""
Удаление позиции заказа (DELETE из order_items).

delete_guard покажет зависимость: issued_tickets.order_item_id — NO ACTION
(заблокирует удаление, если по позиции уже выданы билеты).

ВНИМАНИЕ: необратимо.

Запуск:  python sales/delete_order-item.py
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
        ui.header("Удаление позиции заказа")
        oid = crud.pick_id(conn, "orders")
        if oid is None:
            return 0
        rows = db.query(conn, "SELECT id, ticket_id, quantity, total_price FROM order_items WHERE order_id=%s ORDER BY id;", (oid,))
        crud.print_rows(rows, max_width=30)
        if not rows:
            return 0
        iid = ui.ask_int("ID позиции для удаления")
        if iid is None or not any(r["id"] == iid for r in rows):
            print(ui.warn("  Позиция не найдена у этого заказа."))
            return 0
        deps = delete_guard.collect_dependencies(conn, "order_items", iid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить позицию id={iid}?"):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM order_items WHERE id=%s;", (iid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
