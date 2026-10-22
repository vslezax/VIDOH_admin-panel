"""
Просмотр пользователей (таблица users).

Запуск:  python users/view_users.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("pending", "active", "blocked", "deleted")


def list_users(conn) -> None:
    ui.header("Пользователи")
    status = ui.ask("Фильтр по статусу (или Enter)", default="").strip().lower()
    search = ui.ask("Поиск по email/name/nickname (или Enter)", default="").strip()
    where, params = [], []
    if status in STATUSES:
        where.append("status = %s")
        params.append(status)
    if search:
        where.append("(email::text ILIKE %s OR name ILIKE %s OR nickname ILIKE %s)")
        params += [f"%{search}%"] * 3
    rows = crud.list_rows(
        conn, "users",
        columns=["id", "email", "phone", "name", "nickname", "status", "created_at"],
        where=" AND ".join(where) if where else "", params=params, limit=50,
    )
    ui.section(f"Найдено: {len(rows)}")
    crud.print_rows(rows, max_width=36)


def show_card(conn) -> None:
    ui.header("Карточка пользователя")
    uid = crud.pick_id(conn, "users")
    if uid is None:
        return
    u = crud.fetch_one(conn, "users", uid)
    ui.section(f"users id={uid}")
    fields = ["uuid", "email", "phone", "name", "nickname", "status",
              "avatar_media_id", "email_verified_at", "phone_verified_at",
              "last_login_at", "created_at", "deleted_at"]
    ui.print_table(["поле", "значение"], [[f, u.get(f)] for f in fields], max_width=60)
    sess = db.query(conn, "SELECT COUNT(*) c FROM user_sessions WHERE user_id=%s AND revoked_at IS NULL;", (uid,))
    print(ui.info(f"  Активных сессий: {sess[0]['c']}"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("VIEW USERS — пользователи", [
                ("1", "Список пользователей"),
                ("2", "Карточка пользователя"),
            ])
            if choice is None:
                break
            try:
                if choice == "1":
                    list_users(conn)
                elif choice == "2":
                    show_card(conn)
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
