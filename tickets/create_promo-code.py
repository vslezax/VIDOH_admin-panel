"""
Создание промокода (INSERT в promo_codes).

Обязательные: code (уникальный), discount_type (enum), discount_value.
CHECK: discount_value > 0; percent -> discount_value <= 100;
       max_uses > 0 и used_count <= max_uses; valid_to > valid_from.

Запуск:  python tickets/create_promo-code.py
"""
from __future__ import annotations

import os
import sys

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
        ui.header("Создание промокода")
        data: dict = {}

        code = ui.ask("code").strip()
        if not code:
            print(ui.fail("  code обязателен."))
            return 0
        data["code"] = code

        ch, event_id = crud.ask_fk(conn, "event_id", "events", label_cols=("title",))
        if ch and event_id is not None:
            data["event_id"] = event_id

        _, dtype = crud.ask_enum("discount_type", DISCOUNT_TYPES, current="percent")
        data["discount_type"] = dtype
        ch, dval = crud.ask_decimal("discount_value", required=True)
        if dval is None:
            print(ui.fail("  discount_value обязателен."))
            return 0
        if dval <= 0 or (dtype == "percent" and dval > 100):
            print(ui.fail("  discount_value нарушает CHECK (>0; percent<=100)."))
            return 0
        data["discount_value"] = dval

        ch, max_uses = crud.ask_int("max_uses", min_value=1)
        if ch and max_uses is not None:
            data["max_uses"] = max_uses
        ch, used = crud.ask_int("used_count", min_value=0)
        data["used_count"] = used if used is not None else 0
        if "max_uses" in data and data["used_count"] > data["max_uses"]:
            print(ui.fail("  used_count не может быть больше max_uses (CHECK)."))
            return 0

        ch, vf = crud.ask_datetime("valid_from")
        if ch:
            data["valid_from"] = vf
        ch, vt = crud.ask_datetime("valid_to")
        if ch:
            data["valid_to"] = vt
        if data.get("valid_from") and data.get("valid_to"):
            if str(data["valid_to"]) <= str(data["valid_from"]):
                print(ui.fail("  valid_to должен быть позже valid_from (CHECK)."))
                return 0

        is_active = ui.ask("is_active? (y/n)", default="y").strip().lower() in ("y", "yes", "1")
        data["is_active"] = is_active

        ui.section("Итог")
        crud.show_diff(data)
        if not ui.confirm("Создать промокод?"):
            print(ui.dim("  Отменено."))
            return 0
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_sql = ", ".join(db.quote_ident(c) for c in cols)
        sql = (f"INSERT INTO promo_codes ({cols_sql}, created_at, updated_at) "
               f"VALUES ({placeholders}, now(), now()) RETURNING id;")
        try:
            rows = db.query(conn, sql, tuple(data.values()))
            print(ui.ok(f"  Создан промокод id={rows[0]['id']}"))
        except Exception as ex:  # noqa: BLE001
            print(ui.fail(f"  Ошибка: {ex}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
