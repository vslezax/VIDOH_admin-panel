"""
Создание события (INSERT в events).

Интерактивный консольный скрипт:
  - запрашивает обязательные поля (slug, title, venue_id ИЛИ online_url);
  - опционально: описание, статус, age_rating, capacity, currency, published_at;
  - генерирует uuid и created_at/updated_at;
  - валидирует CHECK-ограничения (venue или online, age_rating, capacity);
  - показывает итог и требует подтверждения 'yes'.

Запуск:  python events/create_event.py
"""
from __future__ import annotations

import os
import sys
import uuid

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
        ui.header("Создание события")
        data: dict = {}

        _, slug = crud.ask_text("slug (URL-идентификатор)", required=True)
        if not slug:
            print(ui.warn("  slug обязателен."))
            return 1
        data["slug"] = slug

        _, title = crud.ask_text("title", required=True)
        if not title:
            print(ui.warn("  title обязателен."))
            return 1
        data["title"] = title

        # venue_id ИЛИ online_url (CHECK chk_events_venue_or_online)
        _, venue_id = crud.ask_fk(conn, "venue_id", "venues", label_cols=("name",))
        _, online_url = crud.ask_text("online_url (если онлайн-событие)")
        if venue_id is None and not online_url:
            print(ui.warn("  Нужно указать venue_id ИЛИ online_url."))
            return 1
        if venue_id is not None:
            data["venue_id"] = venue_id
        if online_url:
            data["online_url"] = online_url

        _, short = crud.ask_text("short_description")
        if short:
            data["short_description"] = short
        _, desc = crud.ask_text("description")
        if desc:
            data["description"] = desc

        changed, status = crud.ask_enum("status", STATUSES, current="draft")
        data["status"] = status

        raw_age = ui.ask("age_rating (0/6/12/16/18 или Enter — пусто)", default="").strip()
        if raw_age:
            if raw_age not in AGE_RATINGS:
                print(ui.warn("  Недопустимый age_rating — пропускаю."))
            else:
                data["age_rating"] = int(raw_age)

        ch, cap = crud.ask_int("capacity", min_value=0)
        if ch and cap is not None:
            data["capacity"] = cap

        currency = ui.ask("currency", default="RUB").strip().upper() or "RUB"
        data["currency"] = currency

        ch, pub = crud.ask_datetime("published_at")
        if ch:
            data["published_at"] = pub

        data["uuid"] = str(uuid.uuid4())
        data["created_at"] = "now()"
        data["updated_at"] = "now()"

        ui.section("Итог")
        display = {k: v for k, v in data.items() if v != "now()"}
        display["created_at/updated_at"] = "now()"
        crud.show_diff(display)

        if not ui.confirm("Создать событие?"):
            print(ui.dim("  Отменено."))
            return 0

        # created_at/updated_at через now() нельзя передать параметром -> строим SQL вручную
        cols = [c for c in data if c not in ("created_at", "updated_at")]
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (
            f"INSERT INTO events ({cols_sql}, created_at, updated_at) "
            f"VALUES ({placeholders}, now(), now()) RETURNING id;"
        )
        try:
            rows = db.query(conn, sql, tuple(data[c] for c in cols))
            print(ui.ok(f"  Создано событие id={rows[0]['id']}"))
        except Exception as e:  # noqa: BLE001
            print(ui.fail(f"  Ошибка вставки: {e}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
