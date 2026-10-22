"""
Просмотр организаторов (таблица organizers).

Запуск:  python organizers/view_organizers.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

STATUSES = ("draft", "active", "suspended", "archived")


def list_orgs(conn) -> None:
    ui.header("Организаторы")
    status = ui.ask("Фильтр по статусу (или Enter)", default="").strip().lower()
    search = ui.ask("Поиск по name/slug (или Enter)", default="").strip()
    where, params = [], []
    if status in STATUSES:
        where.append("status = %s")
        params.append(status)
    if search:
        where.append("(name ILIKE %s OR slug ILIKE %s)")
        params += [f"%{search}%"] * 2
    rows = crud.list_rows(
        conn, "organizers",
        columns=["id", "slug", "name", "status", "legal_form", "created_at"],
        where=" AND ".join(where) if where else "", params=params, limit=50,
    )
    ui.section(f"Найдено: {len(rows)}")
    crud.print_rows(rows, max_width=40)


def show_card(conn) -> None:
    ui.header("Карточка организатора")
    oid = crud.pick_id(conn, "organizers")
    if oid is None:
        return
    o = crud.fetch_one(conn, "organizers", oid)
    ui.section(f"organizers id={oid}")
    fields = ["slug", "name", "status", "legal_form", "inn", "ogrn",
              "avatar_media_id", "cover_media_id", "short_description", "created_at"]
    ui.print_table(["поле", "значение"], [[f, o.get(f)] for f in fields], max_width=60)
    contacts = db.query(conn, "SELECT id, type, value, is_shown FROM organizer_contacts WHERE organizer_id=%s ORDER BY sort_order, id;", (oid,))
    ui.section("Контакты")
    crud.print_rows(contacts, max_width=40) if contacts else print(ui.dim("  нет"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        while True:
            choice = ui.menu("VIEW ORGANIZERS — организаторы", [
                ("1", "Список организаторов"),
                ("2", "Карточка организатора"),
            ])
            if choice is None:
                break
            try:
                if choice == "1":
                    list_orgs(conn)
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
