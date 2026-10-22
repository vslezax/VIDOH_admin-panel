"""
Управление привязкой медиа к событию (таблица event_media, composite PK).

Интерактивный консольный скрипт:
  - список медиа события (с ролью и порядком);
  - добавить медиа (event_id + media_id, роль, sort_order, caption);
    * соблюдается частичный UNIQUE: одна роль (main/gallery/...) на событие —
      повтор для роли 'gallery' разрешён только если роль не уникальна — уточняем;
  - удалить медиа у события.

Запуск:  python events/manage_event-media.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

ROLES = ("main", "gallery", "logo", "icon", "cover", "avatar")


def list_links(conn, eid: int) -> None:
    rows = db.query(
        conn,
        "SELECT em.media_id, em.role, em.sort_order, em.caption, m.storage_key "
        "FROM event_media em JOIN media m ON m.id=em.media_id "
        "WHERE em.event_id=%s ORDER BY em.sort_order, m.id;",
        (eid,),
    )
    ui.section(f"Медиа события id={eid}")
    crud.print_rows(rows, max_width=50) if rows else print(ui.dim("  нет"))


def add_link(conn) -> None:
    eid = crud.pick_id(conn, "events")
    if eid is None:
        return
    _, mid = crud.ask_fk(conn, "media_id", "media", label_cols=("storage_key",), allow_null=False)
    if mid is None:
        return
    dup = db.query(conn, "SELECT 1 FROM event_media WHERE event_id=%s AND media_id=%s;", (eid, mid))
    if dup:
        print(ui.warn("  Это медиа уже привязано к событию."))
        return

    _, role = crud.ask_enum("role", ROLES, current="gallery")
    # частичный UNIQUE (event_id, role) — проверяем
    same_role = db.query(conn, "SELECT media_id FROM event_media WHERE event_id=%s AND role=%s;", (eid, role))
    if same_role:
        print(ui.warn(f"  У события уже есть медиа с ролью '{role}' (media_id={same_role[0]['media_id']})."))
        print(ui.dim("  По ограничению uq_event_media_one_role_per_event роль должна быть уникальна."))
        return

    sort_order = ui.ask_int("sort_order", default=0) or 0
    caption = ui.ask("caption (Enter — пусто)", default="").strip() or None

    if not ui.confirm(f"Привязать media id={mid} к событию id={eid} (роль {role})?"):
        print(ui.dim("  Отменено."))
        return
    try:
        db.execute(
            conn,
            "INSERT INTO event_media (event_id, media_id, role, sort_order, caption) VALUES (%s,%s,%s,%s,%s);",
            (eid, mid, role, sort_order, caption),
        )
        print(ui.ok("  Привязано."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def remove_link(conn) -> None:
    eid = crud.pick_id(conn, "events")
    if eid is None:
        return
    list_links(conn, eid)
    mid = ui.ask_int("media_id для отвязки")
    if mid is None:
        return
    if not ui.confirm(f"Отвязать media id={mid} от события id={eid}?"):
        print(ui.dim("  Отменено."))
        return
    try:
        n = db.execute(conn, "DELETE FROM event_media WHERE event_id=%s AND media_id=%s;", (eid, mid))
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
            choice = ui.menu("EVENT MEDIA — привязки медиа", [
                ("1", "Список медиа события"),
                ("2", "Добавить медиа"),
                ("3", "Удалить медиа"),
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
