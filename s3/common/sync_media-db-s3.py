"""
Синхронизация библиотеки медиа: БД (таблица media) <-> S3 (бакет).

Интерактивный консольный скрипт (по умолчанию только анализ):
  - собирает storage_key из таблицы media;
  - собирает ключи объектов в S3 (по префиксу, по умолчанию media/);
  - находит расхождения:
      A) в БД есть, в S3 нет  -> "битые" записи (файл пропал);
      B) в S3 есть, в БД нет  -> "бесхозные" файлы (сироты).
  - по запросу позволяет устранить:
      A) удалить строки из БД (удалить media-записи);
      B) удалить объекты из S3.

Запуск:  python sync_media-db-s3.py
"""
from __future__ import annotations

import os
import sys
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r'..\..'))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import sys

from lib import db, s3, ui

DEFAULT_PREFIX = "media/"


def _load_db_keys(conn) -> dict[str, int]:
    """storage_key -> media.id"""
    rows = db.query(conn, "SELECT id, storage_key FROM media;")
    return {r["storage_key"]: r["id"] for r in rows}


def _load_s3_keys(client, cfg, prefix: str) -> set[str]:
    objs = s3.list_objects(client, cfg.default_bucket, prefix, limit=100000)
    return {o["key"] for o in objs}


def analyze(conn, client, cfg, prefix: str) -> tuple[dict[str, int], set[str]]:
    db_keys = _load_db_keys(conn)
    s3_keys = _load_s3_keys(client, cfg, prefix)
    db_set = set(db_keys)

    ui.header("Анализ расхождений БД <-> S3")
    print(f"  записей в БД:      {len(db_set)}")
    print(f"  объектов в S3 ({prefix}): {len(s3_keys)}")

    db_only = [k for k in db_set if k not in s3_keys]
    s3_only = [k for k in s3_keys if k not in db_set]

    ui.section(f"A) Есть в БД, нет в S3: {len(db_only)}")
    if db_only:
        rows = [[db_keys[k], k] for k in db_only[:50]]
        ui.print_table(["media.id", "storage_key"], rows, max_width=60)
        if len(db_only) > 50:
            print(ui.dim(f"  … и ещё {len(db_only) - 50}"))
    else:
        print(ui.dim("  нет"))

    ui.section(f"B) Есть в S3, нет в БД: {len(s3_only)}")
    if s3_only:
        rows = [[k] for k in sorted(s3_only)[:50]]
        ui.print_table(["storage_key"], rows, max_width=70)
        if len(s3_only) > 50:
            print(ui.dim(f"  … и ещё {len(s3_only) - 50}"))
    else:
        print(ui.dim("  нет"))

    return ({k: db_keys[k] for k in db_only}, s3_only)


def remove_db_only(conn, items: dict[str, int]) -> None:
    if not items:
        print(ui.dim("  Нечего удалять в БД."))
        return
    ui.section(f"Удаление {len(items)} 'битых' записей из БД")
    for k, mid in list(items.items())[:20]:
        print(f"    media.id={mid}: {k}")
    if len(items) > 20:
        print(ui.dim(f"    … и ещё {len(items) - 20}"))
    if not ui.confirm("Удалить эти строки из media? (файлов в S3 нет)"):
        print(ui.dim("  Отменено."))
        return
    ids = list(items.values())
    try:
        # ON DELETE CASCADE у event_media сам почистит привязки
        n = db.execute(conn, "DELETE FROM media WHERE id = ANY(%s);", (ids,))
        print(ui.ok(f"  Удалено строк: {n}"))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка: {e}"))


def remove_s3_only(client, cfg, keys: set[str]) -> None:
    if not keys:
        print(ui.dim("  Нечего удалять в S3."))
        return
    ui.section(f"Удаление {len(keys)} 'бесхозных' файлов из S3")
    for k in sorted(keys)[:20]:
        print(f"    {k}")
    if len(keys) > 20:
        print(ui.dim(f"    … и ещё {len(keys) - 20}"))
    if not ui.confirm("Удалить эти объекты из S3?"):
        print(ui.dim("  Отменено."))
        return
    deleted = 0
    failed = 0
    for k in keys:
        try:
            client.delete_object(Bucket=cfg.default_bucket, Key=k)
            deleted += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(ui.fail(f"    {k}: {s3.friendly_error(e)}"))
    print(ui.ok(f"  Удалено объектов: {deleted}") + (f", ошибок: {failed}" if failed else ""))


def main() -> int:
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1

    ok, reason = s3.is_configured()
    if not ok:
        ui.header("SYNC MEDIA DB<->S3")
        s3.print_not_configured(reason)
        conn.close()
        return 1
    cfg = s3.load_config()
    client = s3.make_client(cfg)
    try:
        client.head_bucket(Bucket=cfg.default_bucket)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Нет доступа к бакету '{cfg.default_bucket}': {s3.friendly_error(e)}"))
        conn.close()
        return 1

    try:
        prefix = ui.ask("Префикс для сравнения", default=DEFAULT_PREFIX)
        db_only, s3_only = analyze(conn, client, cfg, prefix)

        if db_only or s3_only:
            ui.section("Действия")
            if ui.ask("Удалить 'битые' записи из БД? (y/n)", default="n").lower() == "y":
                remove_db_only(conn, db_only)
            if ui.ask("Удалить 'бесхозные' файлы из S3? (y/n)", default="n").lower() == "y":
                remove_s3_only(client, cfg, s3_only)
        else:
            print(ui.ok("\n  БД и S3 синхронизированы — расхождений нет."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Ошибка: {e}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())