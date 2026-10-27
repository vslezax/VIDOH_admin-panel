"""
Создание заказа (INSERT в orders).

Обязательные: user_id (FK), event_id (FK). status DEFAULT 'pending',
total_amount DEFAULT 0. uuid генерируется.
CHECK: total_amount >= 0.
promo_code_id — опционально (SET NULL при удалении промокода).

Запуск:  python sales/create_order.py
"""
from __future__ import annotations

import os
import sys
import uuid

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
        ui.header("Создание заказа")
        data: dict = {"uuid": str(uuid.uuid4())}

        _, user_id = crud.ask_fk(conn, "user_id", "users", label_cols=("email",), allow_null=False)
        if user_id is None:
            return 0
        data["user_id"] = user_id
        _, event_id = crud.ask_fk(conn, "event_id", "events", label_cols=("title",), allow_null=False)
        if event_id is None:
            return 0
        data["event_id"] = event_id

        _, status = crud.ask_enum("status", STATUSES, current="pending")
        data["status"] = status
        ch, total = crud.ask_decimal("total_amount", current=0)
        data["total_amount"] = total if total is not None else 0
        if data["total_amount"] < 0:
            print(ui.fail("  total_amount >= 0 (CHECK)."))
            return 0
        currency = ui.ask("currency", default="RUB").strip().upper() or "RUB"
        if len(currency) != 3:
            print(ui.fail("  currency должен быть ровно 3 символа (CHAR(3))."))
            return 0
        data["currency"] = currency
        ch, promo_id = crud.ask_fk(conn, "promo_code_id", "promo_codes", label_cols=("code",))
        if ch and promo_id is not None:
            data["promo_code_id"] = promo_id

        ch, paid_at = crud.ask_datetime("paid_at")
        if ch and paid_at:
            data["paid_at"] = paid_at
        ch, cancelled_at = crud.ask_datetime("cancelled_at")
        if ch and cancelled_at:
            data["cancelled_at"] = cancelled_at
        if data["status"] == "paid" and not data.get("paid_at"):
            print(ui.fail("  Для status='paid' нужен paid_at (CHECK)."))
            return 0
        if data["status"] == "cancelled" and not data.get("cancelled_at"):
            print(ui.fail("  Для status='cancelled' нужен cancelled_at (CHECK)."))
            return 0

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать заказ?"):
            print(ui.dim("  Отменено."))
            return 0
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO orders ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан заказ id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
