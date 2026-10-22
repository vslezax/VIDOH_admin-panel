"""
Создание страны (INSERT в countries).

Обязательные: name, iso (2 символа, уникален). id генерируется автоматически.

Запуск:  python catalog/create_country.py
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
        ui.header("Создание страны")
        _, name = crud.ask_text("name", required=True)
        if not name:
            print(ui.warn("  name обязателен."))
            return 0
        iso = ui.ask("iso (2 буквы, напр. RU)").strip().upper()
        if len(iso) != 2:
            print(ui.fail("  iso должен быть из 2 символов."))
            return 0
        data = {"name": name, "iso": iso}
        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать страну?"):
            print(ui.dim("  Отменено."))
            return 0
        nid = crud.run_insert(conn, "countries", data)
        if nid is not None:
            print(ui.ok(f"  Создана страна id={nid}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
