"""
Управление привязкой организаторов к событию (таблица event_organizers, composite PK).

Интерактивный консольный скрипт:
  - список организаторов события;
  - добавить организатора (event_id + organizer_id, флаг is_primary, role);
    * соблюдается частичный UNIQUE: один primary-организатор на событие;
  - удалить организатора у события.

Запуск:  python events/manage_event-organizers.py
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
        "SELECT eo.organizer_id, o.name, eo.is_primary, eo.role "
        "FROM event_organizers eo JOIN organizers o ON o.id=eo.organizer_id "
        "WHERE eo.event_id=%s ORDER BY eo.sort_order, o.name;",
        (eid,),
    )
    ui.section(f"Организаторы события id={eid}")
    crud.print_rows(rows, max_width=40) if rows else print(ui.dim("  нет"))


def add_link(conn) -> None:
    eid = crud.pick_id(conn, "events")
    if eid is None:
        return
    _, oid = crud.ask_fk(conn, "organizer_id", "organizers", label_cols=("name",), allow_null=False)
    if oid is None:
        return
    dup = db.query(conn, "SELECT 1 FROM event_organizers WHERE event_id=%s AND organizer_id=%s;", (eid, oid))
    if dup:
        print(ui.warn("  Этот организатор уже привязан к событию."))
        return

    is_primary = ui.ask("Сделать основным (is_primary)? (y/n)", default="n").strip().lower() == "y"
    if is_primary:
        existing = db.query(conn, "SELECT organizer_id FROM event_organizers WHERE event_id=%s AND is_primary;", (eid,))
        if existing:
            print(ui.warn(f"  У события уже есть основной организатор (id={existing[0]['organizer_id']})."))
            if not ui.confirm("Заменить его?"):
                return
            db.execute(conn, "UPDATE event_organizers SET is_primary=FALSE WHERE event_id=%s;", (eid,))

    role = ui.ask("role (текст, Enter — пусто)", default="").strip() or None
    sort_order = ui.ask_int("sort_order", default=0) or 0
    if not ui.confirm(f"Привязать организатора id={oid} к событию id={eid}?"):
        print(ui.dim("  Отменено."))
        return
    try:
        db.execute(
            conn,
            "INSERT INTO event_organizers (event_id, organizer_id, is_primary, role, sort_order) "
            "VALUES (%s,%s,%s,%s,%s);",
            (eid, oid, is_primary, role, sort_order),
        )
        print(ui.ok("  Привязано."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def remove_link(conn) -> None:
    eid = crud.pick_id(conn, "events")
    if eid is None:
        return
    list_links(conn, eid)
    oid = ui.ask_int("organizer_id для отвязки")
    if oid is None:
        return
    if not ui.confirm(f"Отвязать организатора id={oid} от события id={eid}?"):
        print(ui.dim("  Отменено."))
        return
    try:
        n = db.execute(conn, "DELETE FROM event_organizers WHERE event_id=%s AND organizer_id=%s;", (eid, oid))
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
            choice = ui.menu("EVENT ORGANIZERS — привязки организаторов", [
                ("1", "Список организаторов события"),
                ("2", "Добавить организатора"),
                ("3", "Удалить организатора"),
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
