"""
Просмотр станций метро (таблица metro_stations).

Запуск:  python catalog/view_metro-stations.py
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
        ui.header("Станции метро")
        city_id = ui.ask_int("Фильтр по city_id (Enter — все)", default=None)
        where = ""
        params = []
        if city_id is not None:
            where = "WHERE ms.city_id=%s"
            params.append(city_id)

        rows = db.query(
            conn,
            "SELECT ms.id, ms.city_id, c.name AS city, ms.name, ms.line_name, "
            "       ms.line_color, ms.line_icon_media_id, ms.sort_order, ms.deleted_at "
            "FROM metro_stations ms "
            "JOIN cities c ON c.id=ms.city_id "
            f"{where} "
            "ORDER BY c.name, ms.line_name, ms.sort_order, ms.name;",
            tuple(params),
        )
        ui.section(f"Найдено: {len(rows)}")
        crud.print_rows(rows, max_width=40) if rows else print(ui.dim("  нет"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
