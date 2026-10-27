"""
Редактирование промокода (UPDATE promo_codes).

Запуск:  python tickets/edit_promo-code.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import crud, db, ui

DISCOUNT_TYPES = ("percent", "fixed")


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        ui.header("Редактирование промокода")
        pid = crud.pick_id(conn, "promo_codes")
        if pid is None:
            return 0
        p = crud.fetch_one(conn, "promo_codes", pid)
        ui.print_table(["поле", "значение"],
                       [["code", p["code"]], ["event_id", p["event_id"]], ["discount_type", p["discount_type"]],
                        ["discount_value", p["discount_value"]], ["max_uses", p["max_uses"]],
                        ["used_count", p["used_count"]], ["valid_from", p["valid_from"]],
                        ["valid_to", p["valid_to"]], ["is_active", p["is_active"]]], max_width=60)
        updates: dict = {}

        ch, val = crud.ask_text("code", p["code"])
        if ch and val:
            updates["code"] = val
        ch, val = crud.ask_fk(conn, "event_id", "events", current=p["event_id"], label_cols=("title",))
        if ch:
            updates["event_id"] = val
        ch, val = crud.ask_enum("discount_type", DISCOUNT_TYPES, current=p["discount_type"])
        if ch:
            updates["discount_type"] = val
        ch, val = crud.ask_decimal("discount_value", p["discount_value"])
        if ch and val is not None:
            updates["discount_value"] = val
        ch, val = crud.ask_int("max_uses", p["max_uses"], min_value=1)
        if ch:
            updates["max_uses"] = val
        ch, val = crud.ask_int("used_count", p["used_count"], min_value=0)
        if ch and val is not None:
            updates["used_count"] = val
        ch, val = crud.ask_datetime("valid_from", p["valid_from"])
        if ch:
            updates["valid_from"] = val
        ch, val = crud.ask_datetime("valid_to", p["valid_to"])
        if ch:
            updates["valid_to"] = val
        ch, val = crud.ask_bool("is_active", p["is_active"])
        if ch:
            updates["is_active"] = val

        # Сводная проверка CHECK на итоговых значениях
        dtype = updates.get("discount_type", p["discount_type"])
        dval = updates.get("discount_value", p["discount_value"])
        max_uses = updates.get("max_uses", p["max_uses"])
        used = updates.get("used_count", p["used_count"])
        vf = updates.get("valid_from", p["valid_from"])
        vt = updates.get("valid_to", p["valid_to"])
        if dval is not None and (dval <= 0 or (dtype == "percent" and dval > 100)):
            print(ui.fail("  discount_value нарушает CHECK (>0; percent<=100)."))
            return 0
        if max_uses is not None and used is not None and used > max_uses:
            print(ui.fail("  used_count не может быть больше max_uses (CHECK)."))
            return 0
        if vf and vt and str(vt) <= str(vf):
            print(ui.fail("  valid_to должен быть позже valid_from (CHECK)."))
            return 0

        if not updates:
            print(ui.dim("  Изменений нет."))
            return 0
        crud.show_diff(updates, before=p)
        if not ui.confirm("Применить?"):
            print(ui.dim("  Отменено."))
            return 0
        updates["updated_at"] = datetime.now()
        n = crud.run_update(conn, "promo_codes", pid, updates)
        print(ui.ok(f"  Обновлено строк: {n}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
