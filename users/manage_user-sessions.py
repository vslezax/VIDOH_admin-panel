"""
Управление сессиями пользователей (таблица user_sessions).

Интерактивный консольный скрипт:
  - список сессий пользователя (в т.ч. активные/отозванные);
  - создать сессию вручную (refresh_token_hash, user_agent, ip, expires_at);
  - отозвать сессию (revoked_at = now());
  - удалить сессию.

Запуск:  python users/manage_user-sessions.py
"""
from __future__ import annotations

import ipaddress
import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui


def _user_id(conn) -> int | None:
    return crud.pick_id(conn, "users")


def list_sessions(conn, uid: int) -> list[dict]:
    rows = db.query(
        conn,
        "SELECT id, user_agent, ip, expires_at, revoked_at, created_at "
        "FROM user_sessions WHERE user_id=%s ORDER BY created_at DESC;",
        (uid,),
    )
    ui.section(f"Сессии пользователя id={uid}")
    crud.print_rows(rows, max_width=36) if rows else print(ui.dim("  нет"))
    return rows


def create_session(conn) -> None:
    uid = _user_id(conn)
    if uid is None:
        return
    token = ui.ask("refresh_token_hash").strip()
    if not token:
        print(ui.fail("  refresh_token_hash обязателен."))
        return
    ua = ui.ask("user_agent (Enter — пусто)", default="").strip() or None
    ip = ui.ask("ip (Enter — пусто)", default="").strip() or None
    if ip is not None:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            print(ui.fail("  ip должен быть валидным IPv4/IPv6 (INET)."))
            return
    ch, expires = crud.ask_datetime("expires_at")
    if not expires:
        print(ui.fail("  expires_at обязателен."))
        return
    data = {"user_id": uid, "refresh_token_hash": token, "user_agent": ua, "ip": ip, "expires_at": expires}
    ui.section("Итог")
    crud.show_diff(data)
    if not ui.confirm("Создать сессию?"):
        print(ui.dim("  Отменено."))
        return
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    cols_sql = ", ".join(db.quote_ident(c) for c in cols)
    sql = f"INSERT INTO user_sessions ({cols_sql}, created_at) VALUES ({placeholders}, now()) RETURNING id;"
    try:
        rows = db.query(conn, sql, tuple(data.values()))
        print(ui.ok(f"  Создана сессия id={rows[0]['id']}"))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def revoke_session(conn) -> None:
    uid = _user_id(conn)
    if uid is None:
        return
    rows = list_sessions(conn, uid)
    if not rows:
        return
    sid = ui.ask_int("ID сессии для отзыва")
    if sid is None or not any(r["id"] == sid for r in rows):
        print(ui.warn("  Сессия не найдена."))
        return
    if not ui.confirm(f"Отозвать сессию id={sid}?"):
        print(ui.dim("  Отменено."))
        return
    try:
        n = db.execute(conn, "UPDATE user_sessions SET revoked_at=now() WHERE id=%s AND revoked_at IS NULL;", (sid,))
        print(ui.ok(f"  Отозвано сессий: {n}"))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def delete_session(conn) -> None:
    uid = _user_id(conn)
    if uid is None:
        return
    rows = list_sessions(conn, uid)
    if not rows:
        return
    sid = ui.ask_int("ID сессии для удаления")
    if sid is None or not any(r["id"] == sid for r in rows):
        print(ui.warn("  Сессия не найдена."))
        return
    if not ui.confirm(f"Удалить сессию id={sid}?"):
        print(ui.dim("  Отменено."))
        return
    n = db.execute(conn, "DELETE FROM user_sessions WHERE id=%s;", (sid,))
    print(ui.ok(f"  Удалено строк: {n}"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("USER SESSIONS — сессии пользователя", [
                ("1", "Список сессий"),
                ("2", "Создать сессию"),
                ("3", "Отозвать сессию"),
                ("4", "Удалить сессию"),
            ])
            if choice is None:
                break
            try:
                if choice == "1":
                    uid = _user_id(conn)
                    if uid is not None:
                        list_sessions(conn, uid)
                elif choice == "2":
                    create_session(conn)
                elif choice == "3":
                    revoke_session(conn)
                elif choice == "4":
                    delete_session(conn)
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
