"""
Просмотр событий (таблица events).

Интерактивный консольный скрипт (только чтение):
  - сводка по событиям (всего, по статусам);
  - список событий с фильтрами (статус, поиск по title/slug);
  - карточка события: поля, площадка, организаторы, категории, медиа, ссылки.

Запуск:  python events/view_events.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("unpublished", "published", "cancelled", "finished")


def show_summary(conn) -> None:
    ui.header("Сводка по событиям")
    total = db.query(conn, "SELECT COUNT(*) c FROM events;")[0]["c"]
    by_status = db.query(conn, "SELECT status, COUNT(*) c FROM events GROUP BY status ORDER BY status;")
    ui.print_table(["статус", "кол-во"], [[r["status"], r["c"]] for r in by_status], max_width=20)
    print(ui.ok(f"\n  Всего событий: {total}"))


def list_events(conn) -> None:
    ui.header("Список событий")
    status = ui.ask("Фильтр по статусу (или Enter)", default="").strip().lower()
    search = ui.ask("Поиск по title/slug (или Enter)", default="").strip()
    limit = ui.ask_int("Сколько показать", default=30) or 30

    where, params = [], []
    if status in STATUSES:
        where.append("status = %s")
        params.append(status)
    if search:
        where.append("(title ILIKE %s OR slug ILIKE %s)")
        params += [f"%{search}%"] * 2

    rows = crud.list_rows(
        conn, "events",
        columns=["id", "title", "status", "venue_id", "published_at", "created_at"],
        where=" AND ".join(where) if where else "",
        params=params, order="id DESC", limit=limit,
    )
    ui.section(f"Найдено: {len(rows)}")
    crud.print_rows(rows, max_width=40)


def show_card(conn) -> None:
    ui.header("Карточка события")
    eid = crud.pick_id(conn, "events")
    if eid is None:
        return
    e = crud.fetch_one(conn, "events", eid)
    ui.section(f"events id={eid}")
    fields = ["slug", "title", "status", "venue_id", "online_url", "age_rating",
              "capacity", "currency", "published_at", "short_description", "created_at"]
    ui.print_table(["поле", "значение"], [[f, e.get(f)] for f in fields], max_width=60)

    # Площадка
    if e.get("venue_id"):
        v = db.query(conn,
            "SELECT v.name, c.name AS city FROM venues v LEFT JOIN cities c ON c.id=v.city_id WHERE v.id=%s;",
            (e["venue_id"],))
        if v:
            print(ui.info(f"  Площадка: {v[0]['name']} ({v[0]['city'] or '-'})"))

    # Организаторы
    orgs = db.query(conn,
        "SELECT o.id, o.name, eo.is_primary FROM event_organizers eo "
        "JOIN organizers o ON o.id=eo.organizer_id WHERE eo.event_id=%s ORDER BY o.id;", (eid,))
    ui.section("Организаторы")
    crud.print_rows(orgs, max_width=40) if orgs else print(ui.dim("  нет"))

    # Категории
    cats = db.query(conn,
        "SELECT c.id, c.name FROM event_categories ec JOIN categories c ON c.id=ec.category_id "
        "WHERE ec.event_id=%s ORDER BY c.id;", (eid,))
    ui.section("Категории")
    crud.print_rows(cats, max_width=40) if cats else print(ui.dim("  нет"))

    # Медиа
    media = db.query(conn,
        "SELECT em.media_id, em.role, m.storage_key FROM event_media em "
        "JOIN media m ON m.id=em.media_id WHERE em.event_id=%s ORDER BY em.sort_order;", (eid,))
    ui.section("Медиа")
    crud.print_rows(media, max_width=50) if media else print(ui.dim("  нет"))

    # Ссылки
    links = db.query(conn, "SELECT id, type, url, title FROM event_links WHERE event_id=%s ORDER BY sort_order;", (eid,))
    ui.section("Ссылки")
    crud.print_rows(links, max_width=50) if links else print(ui.dim("  нет"))


ACTIONS = {
    "1": ("Сводка по событиям", show_summary),
    "2": ("Список событий", list_events),
    "3": ("Карточка события", show_card),
}


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("VIEW EVENTS — события", [(k, lbl) for k, (lbl, _) in ACTIONS.items()])
            if choice is None:
                print(ui.dim("Пока."))
                break
            if choice in ACTIONS:
                try:
                    ACTIONS[choice][1](conn)
                except Exception as e:  # noqa: BLE001
                    print(ui.fail(f"Ошибка: {e}"))
            else:
                print(ui.warn("Нет такого пункта."))
            ui.pause()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
