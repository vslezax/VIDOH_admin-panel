"""
Удаление расписания события (DELETE из event_schedules). Зависимостей нет.

Запуск:  python events/delete_event-schedule.py
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
        ui.header("Удаление расписания события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        rows = db.query(conn, "SELECT id, kind, start_at, recurrence FROM event_schedules WHERE event_id=%s ORDER BY id;", (eid,))
        crud.print_rows(rows, max_width=40)
        if not rows:
            return 0
        sid = ui.ask_int("ID расписания для удаления")
        if sid is None or not any(r["id"] == sid for r in rows):
            print(ui.warn("  Расписание не найдено у этого события."))
            return 0
        deps = delete_guard.collect_dependencies(conn, "event_schedules", sid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить расписание id={sid}?"):
            print(ui.dim("  Отменено."))
            return 0
        n = db.execute(conn, "DELETE FROM event_schedules WHERE id=%s;", (sid,))
        print(ui.ok(f"  Удалено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
