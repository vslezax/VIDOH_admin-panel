"""
Изменение статуса платежа (UPDATE payments.status).

Позволяет вручную перевести платёж в новый статус (например, после
разбора инцидента). CHECK amount>0 не затрагивается.

Запуск:  python sales/edit_payment-status.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("pending", "succeeded", "failed", "refunded", "cancelled")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Изменение статуса платежа")
        oid = crud.pick_id(conn, "orders")
        if oid is None:
            return 0
        rows = db.query(conn, "SELECT id, provider, amount, status, created_at FROM payments WHERE order_id=%s ORDER BY id;", (oid,))
        crud.print_rows(rows, max_width=40)
        if not rows:
            return 0
        pid = ui.ask_int("ID платежа")
        if pid is None:
            return 0
        p = next((r for r in rows if r["id"] == pid), None)
        if not p:
            print(ui.fail("  Платёж не найден у этого заказа."))
            return 0

        ui.section(f"Текущий статус: {p['status']}")
        _, new_status = crud.ask_enum("Новый статус", STATUSES, current=p["status"])
        if new_status == p["status"]:
            print(ui.dim("  Статус не изменился."))
            return 0

        ui.section("Изменение")
        ui.print_table(["поле", "было → станет"], [["status", f"{p['status']} → {new_status}"]], max_width=50)
        if not ui.confirm(f"Сменить статус платежа id={pid}?"):
            print(ui.dim("  Отменено."))
            return 0
        n = crud.run_update(conn, "payments", pid, {"status": new_status})
        print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
