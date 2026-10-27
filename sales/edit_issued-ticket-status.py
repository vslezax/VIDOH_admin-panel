"""
Изменение статуса выданного билета (UPDATE issued_tickets).

Сценарии: check-in (used + checked_in_at=now()), отмена (cancelled),
возврат (refunded), перевыпуск (active, checked_in_at=NULL).
CHECK: status='used' <-> checked_in_at NOT NULL — соблюдается автоматически.

Запуск:  python sales/edit_issued-ticket-status.py
"""
from __future__ import annotations

import os
import sys

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
        ui.header("Изменение статуса выданного билета")
        tid = crud.pick_id(conn, "issued_tickets")
        if tid is None:
            return 0
        t = crud.fetch_one(conn, "issued_tickets", tid)
        ui.print_table(["поле", "значение"],
                       [["code", t["code"]], ["status", t["status"]], ["checked_in_at", t["checked_in_at"]],
                        ["user_id", t["user_id"]], ["event_id", t["event_id"]]], max_width=60)

        _, new_status = crud.ask_enum("Новый статус", STATUSES, current=t["status"])
        if new_status == t["status"]:
            print(ui.dim("  Статус не изменился."))
            return 0

        if new_status == "used":
            set_sql = "status='used', checked_in_at=now(), updated_at=now()"
            params = []
            preview = "status -> used, checked_in_at -> now()"
        else:
            set_sql = "status=%s, checked_in_at=NULL, updated_at=now()"
            params = [new_status]
            preview = f"status -> {new_status}, checked_in_at -> NULL"

        ui.section("Изменение")
        print(ui.info(f"  {preview}"))
        if not ui.confirm(f"Применить к билету id={tid}?"):
            print(ui.dim("  Отменено."))
            return 0
        try:
            db.execute(conn, f"UPDATE issued_tickets SET {set_sql} WHERE id=%s;", params + [tid])
            print(ui.ok("  Обновлено."))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
