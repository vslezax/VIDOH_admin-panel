"""
Просмотр библиотеки медиа (таблица media).

Интерактивный консольный скрипт (только чтение):
  - сводка по медиа (всего, по типам, суммарный размер);
  - список записей с фильтрами (тип, загрузивший, поиск по ключу/url/alt);
  - карточка одного медиа: поля + привязки (event_media, аватары и т.п.);
  - проверка наличия объекта в S3 для каждой записи (по флагу).

Запуск:  python view_media.py
"""
from __future__ import annotations

import os
import sys
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r'..'))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import sys

from lib import db, s3, ui


def _fmt_row(r: dict) -> list:
    return [
        r["id"],
        r["type"],
        r["storage_key"].split("/")[-1],
        s3.human_size(r["size_bytes"]),
        f'{r["width"]}x{r["height"]}' if r["width"] and r["height"] else "-",
        r["uploaded_by"] or "-",
        (r["created_at"] or "")[:19],
    ]


def show_summary(conn) -> None:
    ui.header("Сводка по медиа")
    total = db.query(conn, "SELECT COUNT(*) c, COALESCE(SUM(size_bytes),0) s FROM media;")[0]
    by_type = db.query(
        conn, "SELECT type, COUNT(*) c, COALESCE(SUM(size_bytes),0) s FROM media GROUP BY type ORDER BY type;"
    )
    rows = [[t["type"], t["c"], s3.human_size(int(t["s"]))] for t in by_type]
    ui.print_table(["тип", "кол-во", "размер"], rows, max_width=20)
    print(ui.ok(f"\n  Всего файлов: {total['c']}, суммарный размер: {s3.human_size(int(total['s']))}"))


def list_media(conn) -> None:
    ui.header("Список медиа")
    type_f = ui.ask("Фильтр по типу (image/video/doc), Enter — все", default="").strip().lower()
    search = ui.ask("Поиск по ключу/url/alt, Enter — без поиска", default="").strip()
    limit = ui.ask_int("Сколько показать", default=50) or 50

    where = []
    params: list = []
    if type_f in ("image", "video", "doc"):
        where.append("type = %s")
        params.append(type_f)
    if search:
        where.append("(storage_key ILIKE %s OR url ILIKE %s OR alt ILIKE %s)")
        params += [f"%{search}%"] * 3

    sql = "SELECT * FROM media"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT %s;"
    params.append(limit)

    rows = db.query(conn, sql, tuple(params))
    ui.section(f"Найдено: {len(rows)}")
    if not rows:
        print(ui.dim("  Ничего не найдено."))
        return
    headers = ["id", "тип", "файл", "размер", "разрешение", "user", "создан"]
    ui.print_table(headers, [_fmt_row(r) for r in rows], max_width=40)


def show_media_card(conn, client, cfg) -> None:
    ui.header("Карточка медиа")
    mid = ui.ask_int("ID медиа")
    if mid is None:
        return
    rows = db.query(conn, "SELECT * FROM media WHERE id=%s;", (mid,))
    if not rows:
        print(ui.fail(f"  Медиа id={mid} не найдено."))
        return
    m = rows[0]

    ui.section(f"media id={m['id']}")
    info_rows = [
        ["storage_key", m["storage_key"]],
        ["url", m["url"]],
        ["type", m["type"]],
        ["alt", m["alt"] or "-"],
        ["width x height", f'{m["width"]} x {m["height"]}' if m["width"] else "-"],
        ["size_bytes", f'{s3.human_size(m["size_bytes"])} ({m["size_bytes"]} B)'],
        ["uploaded_by", m["uploaded_by"] or "-"],
        ["created_at", m["created_at"]],
    ]
    ui.print_table(["поле", "значение"], info_rows, max_width=60)

    # Проверка наличия в S3 (если настроено)
    if client and cfg and cfg.default_bucket:
        try:
            head = client.head_object(Bucket=cfg.default_bucket, Key=m["storage_key"])
            print(ui.ok(f"  Объект в S3: есть ({s3.human_size(head.get('ContentLength'))})"))
        except Exception:  # noqa: BLE001
            print(ui.fail("  Объект в S3: НЕ найден (возможно, удалён вручную)"))

    # Привязки
    ui.section("Привязки")
    bind_rows = []
    em = db.query(conn, "SELECT event_id, role FROM event_media WHERE media_id=%s ORDER BY event_id;", (mid,))
    for r in em:
        bind_rows.append(["event_media", f"event_id={r['event_id']}, role={r['role']}"])
    for tbl, col in [
        ("users", "avatar_media_id"),
        ("organizers", "avatar_media_id"),
        ("organizers", "cover_media_id"),
        ("categories", "icon_media_id"),
    ]:
        found = db.query(conn, f"SELECT id FROM {tbl} WHERE {col}=%s ORDER BY id;", (mid,))
        for r in found:
            bind_rows.append([f"{tbl}.{col}", f"id={r['id']}"])
    if bind_rows:
        ui.print_table(["где", "ссылка"], bind_rows, max_width=50)
    else:
        print(ui.dim("  Медиа ни к чему не привязано."))


ACTIONS = {
    "1": ("Сводка по медиа", "summary"),
    "2": ("Список медиа", "list"),
    "3": ("Карточка медиа", "card"),
}


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1

    client = cfg = None
    if s3.is_configured()[0]:
        try:
            cfg = s3.load_config()
            client = s3.make_client(cfg)
        except Exception:  # noqa: BLE001
            client = cfg = None

    try:
        while True:
            choice = ui.menu(
                "VIEW MEDIA — библиотека медиа",
                [(k, label) for k, (label, _) in ACTIONS.items()],
            )
            if choice is None:
                print(ui.dim("Пока."))
                break
            try:
                if choice == "1":
                    show_summary(conn)
                elif choice == "2":
                    list_media(conn)
                elif choice == "3":
                    show_media_card(conn, client, cfg)
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