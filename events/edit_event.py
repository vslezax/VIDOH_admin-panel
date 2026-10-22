"""
Редактирование события (UPDATE events).

Интерактивный консольный скрипт:
  - выбирает событие по ID и показывает карточку;
  - позволяет изменить: slug, title, short_description, description, venue_id,
    online_url, status, age_rating, capacity, currency, published_at;
  - валидирует CHECK-ограничения и enum-статус;
  - показывает «было → станет» и требует 'yes'.

Запуск:  python events/edit_event.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("draft", "published", "postponed", "cancelled", "finished", "archived")
AGE_RATINGS = ("0", "6", "12", "16", "18")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Редактирование события")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        e = crud.fetch_one(conn, "events", eid)
        ui.section(f"events id={eid}")
        ui.print_table(
            ["поле", "значение"],
            [["title", e["title"]], ["slug", e["slug"]], ["status", e["status"]],
             ["venue_id", e["venue_id"]], ["online_url", e["online_url"]],
             ["age_rating", e["age_rating"]], ["capacity", e["capacity"]],
             ["currency", e["currency"]], ["published_at", e["published_at"]]],
            max_width=60,
        )

        updates: dict = {}

        ch, val = crud.ask_text("title", e["title"])
        if ch:
            if not val:
                print(ui.warn("  title не может быть пустым — пропускаю."))
            else:
                updates["title"] = val

        ch, val = crud.ask_text("slug", e["slug"])
        if ch:
            if not val:
                print(ui.warn("  slug не может быть пустым — пропускаю."))
            else:
                updates["slug"] = val

        ch, val = crud.ask_text("short_description", e["short_description"])
        if ch:
            updates["short_description"] = val
        ch, val = crud.ask_text("description", e["description"])
        if ch:
            updates["description"] = val

        ch, val = crud.ask_fk(conn, "venue_id", "venues", current=e["venue_id"], label_cols=("name",))
        if ch:
            updates["venue_id"] = val
        ch, val = crud.ask_text("online_url", e["online_url"])
        if ch:
            updates["online_url"] = val

        ch, val = crud.ask_enum("status", STATUSES, current=e["status"])
        if ch:
            updates["status"] = val

        raw_age = ui.ask(f"age_rating (текущее: {e['age_rating']}), Enter — оставить, 'null' — очистить")
        if raw_age:
            if raw_age.strip().lower() in crud.NULL_TOKENS:
                updates["age_rating"] = None
            elif raw_age.strip() in AGE_RATINGS:
                updates["age_rating"] = int(raw_age.strip())
            else:
                print(ui.warn("  Недопустимый age_rating — пропускаю."))

        ch, val = crud.ask_int("capacity", e["capacity"], min_value=0)
        if ch:
            updates["capacity"] = val

        raw_cur = ui.ask(f"currency (текущее: {e['currency']}), Enter — оставить").strip().upper()
        if raw_cur:
            updates["currency"] = raw_cur

        ch, val = crud.ask_datetime("published_at", e["published_at"])
        if ch:
            updates["published_at"] = val

        # Проверка venue_or_online после изменений
        new_venue = updates.get("venue_id", e["venue_id"])
        new_online = updates.get("online_url", e["online_url"])
        if new_venue is None and not new_online:
            print(ui.fail("  Нельзя очистить и venue_id, и online_url одновременно (CHECK)."))
            return 0

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0

        ui.section("Изменения")
        crud.show_diff(updates, before=e)
        ui.print_table(["поле", "было → станет"], [])  # noop, для единообразия заголовка

        if not ui.confirm("Применить изменения?"):
            print(ui.dim("  Отменено."))
            return 0

        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if v == 'now()' else '%s'}" for k, v in updates.items()
        )
        params = [v for k, v in updates.items() if v != "now()"] + [eid]
        sql = f"UPDATE events SET {set_clause} WHERE id=%s;"
        try:
            db.execute(conn, sql, params)
            print(ui.ok("  Изменения применены."))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка обновления: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
