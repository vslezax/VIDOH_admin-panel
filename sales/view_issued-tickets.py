"""
Просмотр выданных билетов (таблица issued_tickets).

Запуск:  python sales/view_issued-tickets.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("issued", "used", "cancelled", "refunded")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Выданные билеты")
        status = ui.ask("Фильтр по статусу (или Enter)", default="").strip().lower()
        eid = ui.ask_int("Фильтр по event_id (Enter — все)", default=None)
        where, params = [], []
        if status in STATUSES:
            where.append("status = %s")
            params.append(status)
        if eid is not None:
            where.append("event_id = %s")
            params.append(eid)
        rows = crud.list_rows(
            conn, "issued_tickets",
            columns=["id", "uuid", "order_item_id", "user_id", "event_id", "code", "status", "checked_in_at"],
            where=" AND ".join(where) if where else "", params=params, limit=100,
        )
        ui.section(f"Найдено: {len(rows)}")
        crud.print_rows(rows, max_width=30) if rows else print(ui.dim("  нет"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
