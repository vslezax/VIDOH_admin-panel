"""
Модерация отзыва (UPDATE event_reviews).

Позволяет изменить status (pending/published/rejected).
CHECK: rating между 1 и 5 (не трогаем рейтинг).
UNIQUE(event_id, user_id) — не затрагивается.

Запуск:  python reviews/moderate_reviews.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("pending", "published", "rejected")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Модерация отзыва")
        rid = crud.pick_id(conn, "event_reviews")
        if rid is None:
            return 0
        r = crud.fetch_one(conn, "event_reviews", rid)
        ui.print_table(["поле", "значение"],
                       [["event_id", r["event_id"]], ["user_id", r["user_id"]], ["rating", r["rating"]],
                        ["status", r["status"]]], max_width=60)
        print(ui.info(f"  text: {r['text']}"))

        updates: dict = {}
        ch, val = crud.ask_enum("status", STATUSES, current=r["status"])
        if ch:
            updates["status"] = val

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        ui.section("Изменения")
        crud.show_diff(updates, before=r)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if x == 'now()' else '%s'}" for k, x in updates.items()
        )
        params = [x for x in updates.values() if x != "now()"] + [rid]
        db.execute(conn, f"UPDATE event_reviews SET {set_clause} WHERE id=%s;", params)
        print(ui.ok("  Обновлено."))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
