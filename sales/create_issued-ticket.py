"""
Создание выданного билета (INSERT в issued_tickets).

Обязательные: order_item_id (FK), user_id (FK), event_id (FK), code (уникальный).
status DEFAULT 'active'. CHECK: status='used' -> checked_in_at задан.

Запуск:  python sales/create_issued-ticket.py
"""
from __future__ import annotations

import os
import sys
import uuid

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("active", "used", "cancelled", "refunded")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Создание выданного билета")
        data: dict = {"uuid": str(uuid.uuid4())}

        _, order_item_id = crud.ask_fk(conn, "order_item_id", "order_items",
                                       label_cols=("ticket_name_snapshot",), allow_null=False)
        if order_item_id is None:
            return 0
        data["order_item_id"] = order_item_id
        _, user_id = crud.ask_fk(conn, "user_id", "users", label_cols=("email",), allow_null=False)
        if user_id is None:
            return 0
        data["user_id"] = user_id
        _, event_id = crud.ask_fk(conn, "event_id", "events", label_cols=("title",), allow_null=False)
        if event_id is None:
            return 0
        data["event_id"] = event_id

        code = ui.ask("code (уникальный идентификатор билета)").strip()
        if not code:
            print(ui.fail("  code обязателен."))
            return 0
        data["code"] = code

        _, status = crud.ask_enum("status", STATUSES, current="active")
        data["status"] = status
        if status == "used":
            ch, checked = crud.ask_datetime("checked_in_at (обязателен для 'used')")
            if not checked:
                print(ui.fail("  Для status='used' нужен checked_in_at (CHECK)."))
                return 0
            data["checked_in_at"] = checked
        else:
            data["checked_in_at"] = None

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать билет?"):
            print(ui.dim("  Отменено."))
            return 0
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO issued_tickets ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан билет id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
