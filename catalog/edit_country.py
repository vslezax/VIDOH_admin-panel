"""
Редактирование страны (UPDATE countries).

Запуск:  python catalog/edit_country.py
"""
from __future__ import annotations

import os
import sys

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Редактирование страны")
        cid = crud.pick_id(conn, "countries")
        if cid is None:
            return 0
        c = crud.fetch_one(conn, "countries", cid)
        ui.print_table(["поле", "значение"], [["name", c["name"]], ["iso", c["iso"]]], max_width=60)
        updates: dict = {}
        ch, val = crud.ask_text("name", c["name"])
        if ch and val:
            updates["name"] = val
        raw = ui.ask(f"iso (текущее: {c['iso']}), Enter — оставить").strip().upper()
        if raw:
            if len(raw) != 2:
                print(ui.warn("  iso должен быть из 2 символов — пропускаю."))
            else:
                updates["iso"] = raw
        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        crud.show_diff(updates, before=c)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        n = crud.run_update(conn, "countries", cid, updates)
        print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
