"""
Редактирование расписания события (UPDATE event_schedules).

Запуск:  python events/edit_event-schedule.py
"""
from __future__ import annotations

import os
import re
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

KINDS = ("once", "recurring")
_UTC_RE = re.compile(r"^[+-][0-9]{2}:[0-9]{2}$")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Редактирование расписания события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        rows = db.query(conn, "SELECT * FROM event_schedules WHERE event_id=%s ORDER BY id;", (eid,))
        crud.print_rows(rows, ["id", "kind", "start_at", "recurrence", "utc_offset"], max_width=40)
        if not rows:
            return 0
        sid = ui.ask_int("ID расписания")
        if sid is None:
            return 0
        sch = next((r for r in rows if r["id"] == sid), None)
        if not sch:
            print(ui.fail("  Расписание не найдено у этого события."))
            return 0

        updates: dict = {}
        ch, kind = crud.ask_enum("kind", KINDS, current=sch["kind"])
        if ch:
            updates["kind"] = kind
        new_kind = updates.get("kind", sch["kind"])

        if new_kind == "once":
            ch, start_at = crud.ask_datetime("start_at", sch["start_at"])
            if ch:
                updates["start_at"] = start_at
            updates["recurrence"] = None  # для once recurrence NULL
        else:
            raw = ui.ask(f"recurrence (текущее: {sch['recurrence']}), Enter — оставить").strip()
            if raw:
                updates["recurrence"] = raw
            updates["start_at"] = None

        raw = ui.ask(f"utc_offset (текущее: {sch['utc_offset']}), Enter — оставить").strip()
        if raw:
            if _UTC_RE.match(raw):
                updates["utc_offset"] = raw
            else:
                print(ui.warn("  Формат utc_offset неверен — пропускаю."))

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        ui.section("Изменения")
        crud.show_diff(updates, before=sch)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0

        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if v == 'now()' else '%s'}" for k, v in updates.items()
        )
        params = [v for k, v in updates.items() if v != "now()"] + [sid]
        try:
            db.execute(conn, f"UPDATE event_schedules SET {set_clause} WHERE id=%s;", params)
            print(ui.ok("  Обновлено."))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
