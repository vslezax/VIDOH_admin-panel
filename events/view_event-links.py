"""
Просмотр ссылок событий (таблица event_links). Только чтение.

Запуск:  python events/view_event-links.py
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
        ui.header("Ссылки событий")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        rows = db.query(
            conn,
            "SELECT id, type, url, title, sort_order FROM event_links WHERE event_id=%s ORDER BY sort_order, id;",
            (eid,),
        )
        ui.section(f"event_links для события id={eid}")
        crud.print_rows(rows, max_width=50) if rows else print(ui.dim("  нет"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
