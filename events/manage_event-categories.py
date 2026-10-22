"""
Управление привязкой категорий к событию (таблица event_categories, composite PK).

Интерактивный консольный скрипт:
  - список категорий события;
  - добавить категорию (по event_id + category_id, с флагом is_primary);
    * соблюдается частичный UNIQUE: одна primary-категория на событие;
  - удалить категорию у события.

Запуск:  python events/manage_event-categories.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui


def list_links(conn, eid: int) -> None:
    rows = db.query(
        conn,
        "SELECT ec.category_id, c.name, ec.is_primary, ec.sort_order "
        "FROM event_categories ec JOIN categories c ON c.id=ec.category_id "
        "WHERE ec.event_id=%s ORDER BY ec.sort_order, c.name;",
        (eid,),
    )
    ui.section(f"Категории события id={eid}")
    crud.print_rows(rows, max_width=40) if rows else print(ui.dim("  нет"))


def add_link(conn) -> None:
    eid = crud.pick_id(conn, "events")
    if eid is None:
        return
    _, cid = crud.ask_fk(conn, "category_id", "categories", label_cols=("name",), allow_null=False)
    if cid is None:
        return
    dup = db.query(conn, "SELECT 1 FROM event_categories WHERE event_id=%s AND category_id=%s;", (eid, cid))
    if dup:
        print(ui.warn("  Эта категория уже привязана к событию."))
        return

    is_primary = ui.ask("Сделать основной (is_primary)? (y/n)", default="n").strip().lower() == "y"
    if is_primary:
        existing = db.query(conn, "SELECT category_id FROM event_categories WHERE event_id=%s AND is_primary;", (eid,))
        if existing:
            print(ui.warn(f"  У события уже есть основная категория (id={existing[0]['category_id']})."))
            if not ui.confirm("Заменить её?"):
                return
            db.execute(conn, "UPDATE event_categories SET is_primary=FALSE WHERE event_id=%s;", (eid,))

    sort_order = ui.ask_int("sort_order", default=0) or 0
    if not ui.confirm(f"Привязать категорию id={cid} к событию id={eid}?"):
        print(ui.dim("  Отменено."))
        return
    try:
        db.execute(
            conn,
            "INSERT INTO event_categories (event_id, category_id, is_primary, sort_order) VALUES (%s,%s,%s,%s);",
            (eid, cid, is_primary, sort_order),
        )
        print(ui.ok("  Привязано."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def remove_link(conn) -> None:
    eid = crud.pick_id(conn, "events")
    if eid is None:
        return
    list_links(conn, eid)
    cid = ui.ask_int("category_id для отвязки")
    if cid is None:
        return
    if not ui.confirm(f"Отвязать категорию id={cid} от события id={eid}?"):
        print(ui.dim("  Отменено."))
        return
    try:
        n = db.execute(conn, "DELETE FROM event_categories WHERE event_id=%s AND category_id=%s;", (eid, cid))
        print(ui.ok(f"  Удалено связей: {n}"))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("EVENT CATEGORIES — привязки категорий", [
                ("1", "Список категорий события"),
                ("2", "Добавить категорию"),
                ("3", "Удалить категорию"),
            ])
            if choice is None:
                break
            try:
                if choice == "1":
                    eid = crud.pick_id(conn, "events")
                    if eid is not None:
                        list_links(conn, eid)
                elif choice == "2":
                    add_link(conn)
                elif choice == "3":
                    remove_link(conn)
                else:
                    print(ui.warn("Нет такого пункта."))
            except Exception as e:  # noqa: BLE001
                print(ui.fail(f"Ошибка: {e}"))
            ui.pause()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
