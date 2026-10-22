"""
Управление избранным пользователей (таблица user_favorites, composite PK).

Интерактивный консольный скрипт:
  - список избранных событий пользователя;
  - добавить в избранное (user_id + event_id);
  - удалить из избранного.

Запуск:  python users/manage_user-favorites.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui


def _uid(conn) -> int | None:
    return crud.pick_id(conn, "users")


def list_favs(conn, uid: int) -> list[dict]:
    rows = db.query(
        conn,
        "SELECT uf.event_id, e.title, e.status, uf.created_at "
        "FROM user_favorites uf JOIN events e ON e.id=uf.event_id "
        "WHERE uf.user_id=%s ORDER BY uf.created_at DESC;",
        (uid,),
    )
    ui.section(f"Избранное пользователя id={uid}")
    crud.print_rows(rows, max_width=40) if rows else print(ui.dim("  нет"))
    return rows


def add_fav(conn) -> None:
    uid = _uid(conn)
    if uid is None:
        return
    _, eid = crud.ask_fk(conn, "event_id", "events", label_cols=("title",), allow_null=False)
    if eid is None:
        return
    dup = db.query(conn, "SELECT 1 FROM user_favorites WHERE user_id=%s AND event_id=%s;", (uid, eid))
    if dup:
        print(ui.warn("  Уже в избранном."))
        return
    if not ui.confirm(f"Добавить событие id={eid} в избранное пользователя id={uid}?"):
        print(ui.dim("  Отменено."))
        return
    try:
        db.execute(conn, "INSERT INTO user_favorites (user_id, event_id, created_at) VALUES (%s,%s,now());", (uid, eid))
        print(ui.ok("  Добавлено в избранное."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def remove_fav(conn) -> None:
    uid = _uid(conn)
    if uid is None:
        return
    rows = list_favs(conn, uid)
    if not rows:
        return
    eid = ui.ask_int("event_id для удаления из избранного")
    if eid is None or not any(r["event_id"] == eid for r in rows):
        print(ui.warn("  Этого события нет в избранном пользователя."))
        return
    if not ui.confirm(f"Удалить событие id={eid} из избранного?"):
        print(ui.dim("  Отменено."))
        return
    n = db.execute(conn, "DELETE FROM user_favorites WHERE user_id=%s AND event_id=%s;", (uid, eid))
    print(ui.ok(f"  Удалено связей: {n}"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("USER FAVORITES — избранное", [
                ("1", "Список избранного"),
                ("2", "Добавить в избранное"),
                ("3", "Удалить из избранного"),
            ])
            if choice is None:
                break
            try:
                if choice == "1":
                    uid = _uid(conn)
                    if uid is not None:
                        list_favs(conn, uid)
                elif choice == "2":
                    add_fav(conn)
                elif choice == "3":
                    remove_fav(conn)
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
