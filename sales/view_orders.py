"""
Просмотр заказов (таблица orders).

Запуск:  python sales/view_orders.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("pending", "paid", "cancelled", "refunded", "failed")


def list_orders(conn) -> None:
    ui.header("Заказы")
    status = ui.ask("Фильтр по статусу (или Enter)", default="").strip().lower()
    uid = ui.ask_int("Фильтр по user_id (Enter — все)", default=None)
    where, params = [], []
    if status in STATUSES:
        where.append("status = %s")
        params.append(status)
    if uid is not None:
        where.append("user_id = %s")
        params.append(uid)
    rows = crud.list_rows(
        conn, "orders",
        columns=["id", "user_id", "event_id", "status", "total_amount", "currency", "promo_code_id", "created_at"],
        where=" AND ".join(where) if where else "", params=params, limit=50,
    )
    ui.section(f"Найдено: {len(rows)}")
    crud.print_rows(rows, max_width=30) if rows else print(ui.dim("  нет"))


def show_card(conn) -> None:
    ui.header("Карточка заказа")
    oid = crud.pick_id(conn, "orders")
    if oid is None:
        return
    o = crud.fetch_one(conn, "orders", oid)
    ui.section(f"orders id={oid}")
    fields = ["uuid", "user_id", "event_id", "status", "total_amount", "currency",
              "promo_code_id", "created_at", "paid_at", "cancelled_at"]
    ui.print_table(["поле", "значение"], [[f, o.get(f)] for f in fields], max_width=60)

    items = db.query(
        conn,
        "SELECT id, ticket_id, quantity, unit_price, total_price, ticket_name_snapshot "
        "FROM order_items WHERE order_id=%s ORDER BY id;",
        (oid,),
    )
    ui.section("Позиции заказа")
    crud.print_rows(items, max_width=40) if items else print(ui.dim("  нет"))

    pays = db.query(conn, "SELECT id, provider, amount, status, created_at FROM payments WHERE order_id=%s ORDER BY id;", (oid,))
    ui.section("Платежи")
    crud.print_rows(pays, max_width=40) if pays else print(ui.dim("  нет"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("VIEW ORDERS — заказы", [
                ("1", "Список заказов"),
                ("2", "Карточка заказа"),
            ])
            if choice is None:
                break
            try:
                if choice == "1":
                    list_orders(conn)
                elif choice == "2":
                    show_card(conn)
                else:
                    print(ui.warn("Нет такого пункта."))
            except Exception as e:  # noqa: BLE001
                print(ui.fail(f"Ошибка: {e}"))
            ui.pause()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
