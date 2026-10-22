"""
Удаление типа билета (DELETE из tickets).

delete_guard покажет зависимость: order_items.ticket_id — NO ACTION
(заблокирует удаление, если по билету есть позиции заказов).

ВНИМАНИЕ: необратимо.

Запуск:  python tickets/delete_ticket.py
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
        ui.header("Удаление типа билета")
        eid = crud.pick_id(conn, "events")
        if eid is None:
            return 0
        rows = db.query(conn, "SELECT id, name, price FROM tickets WHERE event_id=%s ORDER BY id;", (eid,))
        crud.print_rows(rows, max_width=30)
        if not rows:
            return 0
        tid = ui.ask_int("ID билета для удаления")
        if tid is None or not any(r["id"] == tid for r in rows):
            print(ui.warn("  Билет не найден у этого события."))
            return 0
        deps = delete_guard.collect_dependencies(conn, "tickets", tid)
        if not delete_guard.report_dependencies(deps):
            return 0
        if not ui.confirm(f"Удалить тип билета id={tid}?"):
            print(ui.dim("  Отменено."))
            return 0
        try:
            n = db.execute(conn, "DELETE FROM tickets WHERE id=%s;", (tid,))
            print(ui.ok(f"  Удалено строк: {n}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
