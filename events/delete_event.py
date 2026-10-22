"""
Удаление события (DELETE из events).

Интерактивный консольный скрипт:
  1. находит событие по ID, показывает карточку;
  2. через delete_guard проверяет зависимые записи и уведомляет:
       - CASCADE: event_media, event_organizers, event_categories,
                  event_links, event_schedules, event_documents, tickets,
                  user_favorites, event_reviews — БУДУТ УДАЛЕНЫ;
       - SET NULL: promo_codes.event_id — будет обнулён;
       - NO ACTION: orders, issued_tickets — ЗАБЛОКИРУЮТ удаление.
  3. требует 'yes';
  4. удаляет строку events (каскад сработает на уровне БД).

ВНИМАНИЕ: операция необратима и затрагивает связанные данные.

Запуск:  python events/delete_event.py
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
        ui.header("Удаление события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        e = crud.fetch_one(conn, "events", eid)
        ui.section("Карточка события")
        ui.print_table(
            ["поле", "значение"],
            [["id", e["id"]], ["title", e["title"]], ["slug", e["slug"]],
             ["status", e["status"]], ["created_at", e["created_at"]]],
            max_width=60,
        )

        ui.section("Проверка зависимых записей")
        deps = delete_guard.collect_dependencies(conn, "events", eid)
        if not delete_guard.report_dependencies(deps):
            return 0

        if not ui.confirm(f"Удалить событие id={eid}? Связанные данные также будут затронуты."):
            print(ui.dim("  Отменено."))
            return 0

        try:
            n = db.execute(conn, "DELETE FROM events WHERE id=%s;", (eid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка удаления: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
