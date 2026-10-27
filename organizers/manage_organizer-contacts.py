"""
Управление контактами организатора (таблица organizer_contacts).

Интерактивный консольный скрипт:
  - список контактов организатора;
  - добавить контакт (type enum, value, is_shown, sort_order);
  - редактировать контакт;
  - удалить контакт.

Запуск:  python organizers/manage_organizer-contacts.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

CONTACT_TYPES = ("phone", "email", "vk", "telegram", "instagram", "website", "other")


def _org(conn) -> int | None:
    return crud.pick_id(conn, "organizers")


def list_contacts(conn, oid: int) -> list[dict]:
    rows = db.query(conn, "SELECT * FROM organizer_contacts WHERE organizer_id=%s ORDER BY sort_order, id;", (oid,))
    ui.section(f"Контакты организатора id={oid}")
    crud.print_rows(rows, ["id", "type", "value", "is_shown", "sort_order"], max_width=40) if rows else print(ui.dim("  нет"))
    return rows


def add_contact(conn) -> None:
    oid = _org(conn)
    if oid is None:
        return
    _, ctype = crud.ask_enum("type", CONTACT_TYPES, current="phone")
    value = ui.ask("value (номер/адрес/ссылка)").strip()
    if not value:
        print(ui.fail("  value обязателен."))
        return
    is_shown = ui.ask("Показывать на сайте (is_shown)? (y/n)", default="y").strip().lower() in ("y", "yes", "1")
    sort_order = ui.ask_int("sort_order", default=0) or 0
    if sort_order < 0:
        print(ui.fail("  sort_order должен быть >= 0 (CHECK)."))
        return
    dup = db.query(
        conn,
        "SELECT 1 FROM organizer_contacts WHERE organizer_id=%s AND type=%s AND value=%s;",
        (oid, ctype, value),
    )
    if dup:
        print(ui.warn("  Такой контакт уже существует (UNIQUE organizer_id, type, value)."))
        return
    data = {"organizer_id": oid, "type": ctype, "value": value, "is_shown": is_shown, "sort_order": sort_order}
    ui.section("Итог")
    crud.show_diff(data)
    if not ui.confirm("Добавить контакт?"):
        print(ui.dim("  Отменено."))
        return
    # created_at через now()
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    cols_sql = ", ".join(db.quote_ident(c) for c in cols)
    sql = f"INSERT INTO organizer_contacts ({cols_sql}, created_at) VALUES ({placeholders}, now()) RETURNING id;"
    try:
        rows = db.query(conn, sql, tuple(data.values()))
        print(ui.ok(f"  Добавлен контакт id={rows[0]['id']}"))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def edit_contact(conn) -> None:
    oid = _org(conn)
    if oid is None:
        return
    rows = list_contacts(conn, oid)
    if not rows:
        return
    cid = ui.ask_int("ID контакта")
    if cid is None:
        return
    c = next((r for r in rows if r["id"] == cid), None)
    if not c:
        print(ui.fail("  Контакт не найден."))
        return
    updates: dict = {}
    ch, val = crud.ask_enum("type", CONTACT_TYPES, current=c["type"])
    if ch:
        updates["type"] = val
    ch, val = crud.ask_text("value", c["value"])
    if ch and val:
        updates["value"] = val
    ch, val = crud.ask_bool("is_shown", c["is_shown"])
    if ch:
        updates["is_shown"] = val
    ch, val = crud.ask_int("sort_order", c["sort_order"], min_value=0)
    if ch and val is not None:
        updates["sort_order"] = val
    if not updates:
        print(ui.dim("  Изменений нет."))
        return
    new_type = updates.get("type", c["type"])
    new_value = updates.get("value", c["value"])
    dup = db.query(
        conn,
        "SELECT 1 FROM organizer_contacts WHERE organizer_id=%s AND type=%s AND value=%s AND id<>%s;",
        (oid, new_type, new_value, c["id"]),
    )
    if dup:
        print(ui.warn("  Такой контакт уже существует (UNIQUE organizer_id, type, value)."))
        return
    crud.show_diff(updates, before=c)
    if not ui.confirm("Применить?"):
        print(ui.dim("  Отменено."))
        return
    n = crud.run_update(conn, "organizer_contacts", cid, updates)
    if n:
        print(ui.ok(f"  Обновлено строк: {n}"))


def delete_contact(conn) -> None:
    oid = _org(conn)
    if oid is None:
        return
    rows = list_contacts(conn, oid)
    if not rows:
        return
    cid = ui.ask_int("ID контакта для удаления")
    if cid is None or not any(r["id"] == cid for r in rows):
        print(ui.warn("  Контакт не найден."))
        return
    if not ui.confirm(f"Удалить контакт id={cid}?"):
        print(ui.dim("  Отменено."))
        return
    n = db.execute(conn, "DELETE FROM organizer_contacts WHERE id=%s;", (cid,))
    print(ui.ok(f"  Удалено строк: {n}"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("ORGANIZER CONTACTS — контакты", [
                ("1", "Список контактов"),
                ("2", "Добавить контакт"),
                ("3", "Редактировать контакт"),
                ("4", "Удалить контакт"),
            ])
            if choice is None:
                break
            try:
                if choice == "1":
                    oid = _org(conn)
                    if oid is not None:
                        list_contacts(conn, oid)
                elif choice == "2":
                    add_contact(conn)
                elif choice == "3":
                    edit_contact(conn)
                elif choice == "4":
                    delete_contact(conn)
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
