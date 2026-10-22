"""
Удаление пользователя (DELETE из users).

delete_guard покажет зависимости:
  - CASCADE: user_sessions, user_favorites, event_reviews — БУДУТ УДАЛЕНЫ;
  - SET NULL: media.uploaded_by — обнулится;
  - NO ACTION: orders, issued_tickets — ЗАБЛОКИРУЮТ удаление.
ВНИМАНИЕ: необратимо.

Запуск:  python users/delete_user.py
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
        ui.header("Удаление пользователя")
        uid = crud.pick_id(conn, "users")
        if uid is None:
            return 0
        u = crud.fetch_one(conn, "users", uid)
        ui.section("Карточка пользователя")
        ui.print_table(["поле", "значение"],
                       [["id", u["id"]], ["email", u["email"]], ["phone", u["phone"]],
                        ["name", u["name"]], ["status", u["status"]]], max_width=60)

        ui.section("Проверка зависимых записей")
        deps = delete_guard.collect_dependencies(conn, "users", uid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить пользователя id={uid}? Связанные данные будут затронуты."):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM users WHERE id=%s;", (uid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка удаления: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
