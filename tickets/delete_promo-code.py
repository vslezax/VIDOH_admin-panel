"""
Удаление промокода (DELETE из promo_codes).

delete_guard покажет зависимость: orders.promo_code_id — SET NULL
(у заказов промокод обнулится).

ВНИМАНИЕ: необратимо.

Запуск:  python tickets/delete_promo-code.py
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
        ui.header("Удаление промокода")
        pid = crud.pick_id(conn, "promo_codes")
        if pid is None:
            return 0
        p = crud.fetch_one(conn, "promo_codes", pid)
        ui.print_table(["поле", "значение"],
                       [["id", p["id"]], ["code", p["code"]], ["discount_type", p["discount_type"]],
                        ["discount_value", p["discount_value"]]], max_width=60)
        deps = delete_guard.collect_dependencies(conn, "promo_codes", pid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить промокод id={pid} ({p['code']})?"):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM promo_codes WHERE id=%s;", (pid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
