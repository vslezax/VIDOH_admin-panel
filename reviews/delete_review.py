"""
Удаление отзыва (DELETE из event_reviews). Зависимостей нет.

ВНИМАНИЕ: необратимо.

Запуск:  python reviews/delete_review.py
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
        ui.header("Удаление отзыва")
        rid = crud.pick_id(conn, "event_reviews")
        if rid is None:
            return 0
        r = crud.fetch_one(conn, "event_reviews", rid)
        ui.print_table(["поле", "значение"],
                       [["id", r["id"]], ["event_id", r["event_id"]], ["user_id", r["user_id"]],
                        ["rating", r["rating"]], ["status", r["status"]]], max_width=60)
        deps = delete_guard.collect_dependencies(conn, "event_reviews", rid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить отзыв id={rid}?"):
            print(ui.dim("  Отменено."))
            return 0
        n = db.execute(conn, "DELETE FROM event_reviews WHERE id=%s;", (rid,))
        print(ui.ok(f"  Удалено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
