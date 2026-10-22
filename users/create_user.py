"""
Создание пользователя (INSERT в users).

CHECK: email ИЛИ phone обязателен (chk_users_email_or_phone).
email — CITEXT (регистронезависимый), уникален. uuid генерируется.

Запуск:  python users/create_user.py
"""
from __future__ import annotations

import os
import sys
import uuid

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
        ui.header("Создание пользователя")
        data: dict = {"uuid": str(uuid.uuid4())}

        email = ui.ask("email (Enter — если есть phone)").strip() or None
        phone = ui.ask("phone (Enter — если есть email)").strip() or None
        if not email and not phone:
            print(ui.fail("  Нужен email ИЛИ phone (CHECK)."))
            return 0
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone

        ch, val = crud.ask_text("password_hash")
        if ch and val:
            data["password_hash"] = val
        ch, val = crud.ask_text("name")
        if ch and val:
            data["name"] = val
        ch, val = crud.ask_text("nickname")
        if ch and val:
            data["nickname"] = val
        ch, val = crud.ask_fk(conn, "avatar_media_id", "media", label_cols=("storage_key",))
        if ch and val is not None:
            data["avatar_media_id"] = val
        _, status = crud.ask_enum("status", STATUSES, current="pending")
        data["status"] = status

        ui.section("Итог")
        display = dict(data)
        if "password_hash" in display:
            display["password_hash"] = "***"
        crud.show_diff(display)
        if not ui.confirm("Создать пользователя?"):
            print(ui.dim("  Отменено."))
            return 0

        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO users ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан пользователь id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
