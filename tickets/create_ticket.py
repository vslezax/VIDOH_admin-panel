"""
Создание типа билета (INSERT в tickets).

Обязательные: event_id (FK), name. price DEFAULT 0.
CHECK: price >= 0, tickets_count >= 0, sold_count >= 0, sold_count <= tickets_count.

Запуск:  python tickets/create_ticket.py
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
        ui.header("Создание типа билета")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        data: dict = {"event_id": eid}
        _, name = crud.ask_text("name", required=True)
        if not name:
            print(ui.warn("  name обязателен."))
            return 0
        data["name"] = name
        ch, val = crud.ask_text("description")
        if ch and val:
            data["description"] = val
        ch, price = crud.ask_decimal("price", required=True)
        data["price"] = price if price is not None else 0
        currency = ui.ask("currency", default="RUB").strip().upper() or "RUB"
        data["currency"] = currency
        ch, cnt = crud.ask_int("tickets_count", min_value=0)
        if ch and cnt is not None:
            data["tickets_count"] = cnt
        ch, sold = crud.ask_int("sold_count", default=0, min_value=0)
        data["sold_count"] = sold if sold is not None else 0
        if "tickets_count" in data and data["tickets_count"] is not None and data["sold_count"] > data["tickets_count"]:
            print(ui.fail("  sold_count не может быть больше tickets_count (CHECK)."))
            return 0
        ch, val = crud.ask_text("external_url")
        if ch and val:
            data["external_url"] = val
        sort_order = ui.ask_int("sort_order", default=0) or 0
        data["sort_order"] = sort_order

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать тип билета?"):
            print(ui.dim("  Отменено."))
            return 0
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO tickets ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан тип билета id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
