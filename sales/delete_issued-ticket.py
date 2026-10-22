"""
Удаление выданного билета (DELETE из issued_tickets). Зависимостей нет.

ВНИМАНИЕ: необратимо. Для «мягкого» аннулирования используйте
edit_issued-ticket-status.py (status=cancelled).

Запуск:  python sales/delete_issued-ticket.py
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
        ui.header("Удаление выданного билета")
        tid = crud.pick_id(conn, "issued_tickets")
        if tid is None:
            return 0
        t = crud.fetch_one(conn, "issued_tickets", tid)
        ui.print_table(["поле", "значение"],
                       [["id", t["id"]], ["code", t["code"]], ["status", t["status"]],
                        ["user_id", t["user_id"]], ["event_id", t["event_id"]]], max_width=60)
        deps = delete_guard.collect_dependencies(conn, "issued_tickets", tid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить билет id={tid} ({t['code']})?"):
            print(ui.dim("  Отменено."))
            return 0
        n = db.execute(conn, "DELETE FROM issued_tickets WHERE id=%s;", (tid,))
        print(ui.ok(f"  Удалено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
