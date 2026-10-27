"""
Управление метаданными медиа (таблица media) — редактирование.

Интерактивный консольный скрипт:
  - выбирает медиа по ID и показывает карточку;
  - позволяет изменить: alt, type, uploaded_by (FK users), width, height;
  - валидирует enum-тип и существование пользователя;
  - не трогает storage_key/url (это технические поля, меняются только вместе с S3);
  - предупреждает, если медиа привязано к событиям (event_media) при смене типа.

Запуск:  python manage_media.py
"""
from __future__ import annotations

import os
import sys
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r'..'))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import sys

from lib import db, s3, ui

EDITABLE = ["alt", "type", "uploaded_by", "width", "height"]
VALID_TYPES = ("image", "video")


def _show_card(conn, mid: int) -> dict | None:
    rows = db.query(conn, "SELECT * FROM media WHERE id=%s;", (mid,))
    if not rows:
        return None
    m = rows[0]
    ui.section(f"media id={m['id']}")
    ui.print_table(
        ["поле", "значение"],
        [
            ["storage_key", m["storage_key"]],
            ["url", m["url"]],
            ["type", m["type"]],
            ["alt", m["alt"] or "-"],
            ["width x height", f'{m["width"]} x {m["height"]}' if m["width"] else "-"],
            ["size_bytes", s3.human_size(m["size_bytes"])],
            ["uploaded_by", m["uploaded_by"] or "-"],
        ],
        max_width=60,
    )
    return m


def _count_bindings(conn, mid: int) -> int:
    em = db.query(conn, "SELECT COUNT(*) c FROM event_media WHERE media_id=%s;", (mid,))
    other = 0
    for tbl, col in [("users", "avatar_media_id"), ("organizers", "avatar_media_id"),
                     ("organizers", "cover_media_id"), ("categories", "icon_media_id"),
                     ("metro_stations", "line_icon_media_id")]:
        r = db.query(conn, f"SELECT COUNT(*) c FROM {tbl} WHERE {col}=%s;", (mid,))
        other += int(r[0]["c"])
    return int(em[0]["c"]) + other


def _ask_optional(prompt: str, current):
    """Возвращает (changed, new_value). Пустой ввод = без изменений."""
    shown = "пусто" if current is None else current
    raw = ui.ask(f"{prompt} (текущее: {shown}), Enter — оставить")
    if raw == "":
        return False, current
    if raw.strip().lower() in ("null", "-", "none"):
        return True, None
    return True, raw


def edit(conn) -> None:
    ui.header("Редактирование медиа")
    mid = ui.ask_int("ID медиа")
    if mid is None:
        return
    m = _show_card(conn, mid)
    if not m:
        print(ui.fail(f"  Медиа id={mid} не найдено."))
        return

    updates: dict[str, object] = {}
    alt = m["alt"]

    # alt
    changed, val = _ask_optional("alt", m["alt"])
    if changed:
        updates["alt"] = val
        alt = val

    # type
    raw = ui.ask(f"type (image/video) (текущее: {m['type']}), Enter — оставить")
    if raw:
        t = raw.strip().lower()
        if t not in VALID_TYPES:
            print(ui.warn(f"  Недопустимый тип '{t}' — пропускаю."))
        elif t != m["type"]:
            updates["type"] = t

    # uploaded_by
    raw = ui.ask(f"uploaded_by (ID пользователя) (текущее: {m['uploaded_by'] or 'пусто'}), Enter — оставить")
    if raw:
        if raw.strip().lower() in ("null", "-", "none"):
            updates["uploaded_by"] = None
        elif raw.isdigit():
            exists = db.query(conn, "SELECT 1 FROM users WHERE id=%s;", (int(raw),))
            if exists:
                updates["uploaded_by"] = int(raw)
            else:
                print(ui.warn(f"  Пользователь id={raw} не найден — пропускаю."))
        else:
            print(ui.warn("  Ожидался числовой ID или 'null' — пропускаю."))

    # width / height
    raw = ui.ask(f"width (текущее: {m['width'] or 'пусто'}), Enter — оставить")
    if raw:
        if raw.strip().lower() in ("null", "-", "none"):
            updates["width"] = None
        elif raw.isdigit() and int(raw) > 0:
            updates["width"] = int(raw)
        else:
            print(ui.warn("  width должен быть > 0 или 'null' — пропускаю."))

    raw = ui.ask(f"height (текущее: {m['height'] or 'пусто'}), Enter — оставить")
    if raw:
        if raw.strip().lower() in ("null", "-", "none"):
            updates["height"] = None
        elif raw.isdigit() and int(raw) > 0:
            updates["height"] = int(raw)
        else:
            print(ui.warn("  height должен быть > 0 или 'null' — пропускаю."))

    if not updates:
        print(ui.dim("  Изменений нет."))
        return

    # Предупреждение при смене типа у привязанного медиа
    if "type" in updates:
        binds = _count_bindings(conn, mid)
        if binds > 0:
            ui.section("Внимание")
            print(ui.warn(f"  Медиа привязано к {binds} объект(ам). Смена типа может нарушить их отображение."))

    ui.section("Итоговые изменения")
    ui.print_table(["поле", "было → станет"], [[k, f"{m.get(k)} → {v}"] for k, v in updates.items()], max_width=50)

    if not ui.confirm("Применить изменения?"):
        print(ui.dim("  Отменено."))
        return

    set_clause = ", ".join(f"{db.quote_ident(k)} = %s" for k in updates)
    params = list(updates.values()) + [mid]
    try:
        n = db.execute(conn, f"UPDATE media SET {set_clause} WHERE id=%s;", params)
        print(ui.ok(f"  Обновлено строк: {n}"))
        _show_card(conn, mid)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка обновления: {e}"))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1
    try:
        edit(conn)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Ошибка: {e}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())