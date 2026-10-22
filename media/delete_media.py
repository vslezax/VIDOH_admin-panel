"""
Удаление медиа: запись в БД + объект из S3.

Интерактивный консольный скрипт:
  1. находит медиа по ID и показывает его карточку;
  2. через delete_guard проверяет зависимые записи (event_media — CASCADE,
     аватары/обложки/иконки — SET NULL) и уведомляет пользователя;
  3. требует явного подтверждения 'yes';
  4. удаляет объект из S3 и строку из media (с возможностью оставить файл в S3).

ВНИМАНИЕ: операция необратима.

Запуск:  python delete_media.py
"""
from __future__ import annotations

import os
import sys
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r'..'))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import sys

from lib import db, delete_guard, s3, ui


def delete(conn, client, cfg) -> None:
    ui.header("Удаление медиа")

    mid = ui.ask_int("ID медиа для удаления")
    if mid is None:
        return

    rows = db.query(conn, "SELECT * FROM media WHERE id=%s;", (mid,))
    if not rows:
        print(ui.fail(f"  Медиа id={mid} не найдено."))
        return
    m = rows[0]

    ui.section("Карточка медиа")
    ui.print_table(
        ["поле", "значение"],
        [
            ["id", m["id"]],
            ["storage_key", m["storage_key"]],
            ["type", m["type"]],
            ["size", s3.human_size(m["size_bytes"])],
            ["url", m["url"]],
        ],
        max_width=60,
    )

    # Проверка зависимостей
    ui.section("Проверка зависимых записей")
    deps = delete_guard.collect_dependencies(conn, "media", mid)
    if not delete_guard.report_dependencies(deps):
        return  # есть блокирующие зависимости

    # Опция оставить файл в S3
    keep_in_s3 = (ui.ask("Оставить файл в S3? (y/n)", default="n").strip().lower() == "y")

    if not ui.confirm(f"Удалить медиа id={mid}? Операция необратима."):
        print(ui.dim("  Отменено."))
        return

    # 1) Удаление из S3 (если не просили оставить)
    if not keep_in_s3 and client and cfg and cfg.default_bucket:
        try:
            client.delete_object(Bucket=cfg.default_bucket, Key=m["storage_key"])
            print(ui.ok(f"  Объект удалён из S3: {m['storage_key']}"))
        except Exception as e:  # noqa: BLE001
            print(ui.fail(f"  Не удалось удалить из S3: {s3.friendly_error(e)}"))
            print(ui.warn("  Прерываю, чтобы не оставить БД и S3 в рассинхроне."))
            return
    elif not keep_in_s3:
        print(ui.warn("  S3 не настроен — удаляю только запись в БД."))

    # 2) Удаление из БД
    try:
        n = db.execute(conn, "DELETE FROM media WHERE id=%s;", (mid,))
        print(ui.ok(f"  Удалено строк из БД: {n}"))
        print(ui.ok("Готово."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка удаления из БД: {e}"))


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
        delete(conn, client, cfg)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Ошибка: {e}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())