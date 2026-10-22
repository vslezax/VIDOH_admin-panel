"""
Создание расписания события (INSERT в event_schedules).

CHECK: kind='once' -> start_at задан, recurrence NULL;
       kind='recurring' -> recurrence задан.
utc_offset формата '+HH:MM' / '-HH:MM'.

Запуск:  python events/create_event-schedule.py
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
        ui.header("Создание расписания события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0

        _, kind = crud.ask_enum("kind", KINDS, current="once")
        data = {"event_id": eid, "kind": kind}

        if kind == "once":
            ch, start_at = crud.ask_datetime("start_at")
            if not start_at:
                print(ui.fail("  Для kind='once' нужен start_at."))
                return 0
            data["start_at"] = start_at
            data["recurrence"] = None
        else:
            rec = ui.ask("recurrence (например 'FREQ=WEEKLY' или текст)").strip()
            if not rec:
                print(ui.fail("  Для kind='recurring' нужен recurrence."))
                return 0
            data["recurrence"] = rec
            data["start_at"] = None

        utc = ui.ask("utc_offset (+HH:MM)", default="+00:00").strip()
        if not _UTC_RE.match(utc):
            print(ui.fail("  Формат utc_offset: +HH:MM или -HH:MM."))
            return 0
        data["utc_offset"] = utc

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать расписание?"):
            print(ui.dim("  Отменено."))
            return 0

        # created_at/updated_at через now()
        cols = ["event_id", "kind", "start_at", "recurrence", "utc_offset"]
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO event_schedules ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data[c] for c in cols))
            print(ui.ok(f"  Создано расписание id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
