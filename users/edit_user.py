"""
Редактирование пользователя (UPDATE users).

Запуск:  python users/edit_user.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("pending", "active", "blocked", "deleted")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Редактирование пользователя")
        uid = crud.pick_id(conn, "users")
        if uid is None:
            return 0
        u = crud.fetch_one(conn, "users", uid)
        ui.print_table(["поле", "значение"],
                       [["email", u["email"]], ["phone", u["phone"]], ["name", u["name"]],
                        ["nickname", u["nickname"]], ["status", u["status"]],
                        ["avatar_media_id", u["avatar_media_id"]]], max_width=60)
        updates: dict = {}

        ch, val = crud.ask_text("email", u["email"])
        if ch:
            updates["email"] = val
        ch, val = crud.ask_text("phone", u["phone"])
        if ch:
            updates["phone"] = val
        ch, val = crud.ask_text("name", u["name"])
        if ch:
            updates["name"] = val
        ch, val = crud.ask_text("nickname", u["nickname"])
        if ch:
            updates["nickname"] = val
        ch, val = crud.ask_fk(conn, "avatar_media_id", "media", current=u["avatar_media_id"], label_cols=("storage_key",))
        if ch:
            updates["avatar_media_id"] = val
        ch, val = crud.ask_enum("status", STATUSES, current=u["status"])
        if ch:
            updates["status"] = val

        # Проверка email OR phone
        new_email = updates.get("email", u["email"])
        new_phone = updates.get("phone", u["phone"])
        if not new_email and not new_phone:
            print(ui.fail("  email и phone не могут быть пустыми одновременно (CHECK)."))
            return 0

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        ui.section("Изменения")
        crud.show_diff(updates, before=u)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0

        updates["updated_at"] = "now()"
        set_clause = ", ".join(
            f"{db.quote_ident(k)} = {'now()' if v == 'now()' else '%s'}" for k, v in updates.items()
        )
        params = [v for k, v in updates.items() if v != "now()"] + [uid]
        try:
            db.execute(conn, f"UPDATE users SET {set_clause} WHERE id=%s;", params)
            print(ui.ok("  Обновлено."))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
