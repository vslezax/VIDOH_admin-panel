"""
Просмотр S3-хранилища VIDOH (Backblaze B2).

Интерактивный консольный скрипт для чтения S3:
  - список доступных бакетов (или бакет из .env, если listBuckets ограничен);
  - список объектов в бакете (с префиксом, размерами);
  - просмотр метаданных одного объекта (размер, тип, last-modified).

Только чтение — ничего не меняет.
Если boto3/креды не настроены, скрипт корректно сообщит об этом и завершится.

Запуск:  python view_s3-storage.py
"""
from __future__ import annotations

import os
import sys
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r'..\..'))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import sys

from lib import s3, ui


def _get_buckets(client, cfg) -> list[str]:
    buckets, source = s3.accessible_buckets(client, cfg)
    if source != "listBuckets":
        print(ui.dim(f"  (listBuckets недоступен, работаем с бакетом из .env: {cfg.default_bucket})"))
    return buckets


def show_buckets(client, cfg) -> None:
    ui.header("Бакеты S3")
    buckets = _get_buckets(client, cfg)
    if not buckets:
        print(ui.dim("  Бакетов нет."))
        return
    rows = []
    for name in buckets:
        mark = " ← (по умолчанию, из .env)" if name == cfg.default_bucket else ""
        rows.append([name, mark])
    ui.print_table(["бакет", "заметка"], rows, max_width=40)
    print(ui.ok(f"\n  Всего бакетов: {len(buckets)}"))


def show_objects(client, cfg) -> None:
    ui.header("Объекты в бакете")
    buckets = _get_buckets(client, cfg)
    if not buckets:
        print(ui.dim("  Бакетов нет."))
        return

    default = cfg.default_bucket if cfg.default_bucket in buckets else buckets[0]
    bucket = ui.ask("Бакет", default=default)
    prefix = ui.ask("Префикс (папка), Enter — все", default="")
    limit = ui.ask_int("Максимум объектов", default=100) or 100

    try:
        objects = s3.list_objects(client, bucket, prefix, limit=limit)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  {s3.friendly_error(e)}"))
        return

    ui.section(f"bucket: {bucket}  prefix: {prefix or '(нет)'}")
    if not objects:
        print(ui.dim("  Объектов не найдено."))
        return

    rows = [
        [o["key"], s3.human_size(o["size"]), o["last_modified"], o["storage_class"]]
        for o in objects
    ]
    ui.print_table(["ключ", "размер", "изменён", "класс"], rows, max_width=50)
    total = sum(o["size"] for o in objects)
    print(ui.ok(f"\n  Объектов: {len(objects)}, суммарно: {s3.human_size(total)}"))


def show_object_meta(client, cfg) -> None:
    ui.header("Метаданные объекта")
    buckets = _get_buckets(client, cfg)
    if not buckets:
        print(ui.dim("  Бакетов нет."))
        return
    default = cfg.default_bucket if cfg.default_bucket in buckets else buckets[0]
    bucket = ui.ask("Бакет", default=default)
    key = ui.ask("Ключ объекта")
    if not key:
        return
    try:
        head = client.head_object(Bucket=bucket, Key=key)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  {s3.friendly_error(e)}"))
        return

    rows = [
        ["key", key],
        ["content-type", head.get("ContentType", "-")],
        ["размер", f"{s3.human_size(head.get('ContentLength'))} ({head.get('ContentLength')} B)"],
        ["last-modified", head.get("LastModified")],
        ["etag", head.get("ETag", "-")],
        ["storage-class", head.get("StorageClass", "-")],
    ]
    for k, v in (head.get("Metadata") or {}).items():
        rows.append([f"meta:{k}", v])
    ui.print_table(["поле", "значение"], rows, max_width=60)


ACTIONS = {
    "1": ("Список бакетов", show_buckets),
    "2": ("Объекты в бакете", show_objects),
    "3": ("Метаданные объекта", show_object_meta),
}


def main() -> int:
    ok, reason = s3.is_configured()
    if not ok:
        ui.header("VIEW S3 STORAGE")
        s3.print_not_configured(reason)
        return 1

    cfg = s3.load_config()
    client = s3.make_client(cfg)

    # Проверка связи: доступ к бакету из .env
    if cfg.default_bucket:
        try:
            client.head_bucket(Bucket=cfg.default_bucket)
        except Exception as e:  # noqa: BLE001
            print(ui.fail(f"Нет доступа к бакету '{cfg.default_bucket}': {s3.friendly_error(e)}"))
            return 1

    try:
        while True:
            choice = ui.menu(
                "VIEW S3 STORAGE — просмотр хранилища",
                [(k, label) for k, (label, _) in ACTIONS.items()],
            )
            if choice is None:
                print(ui.dim("Пока."))
                break
            if choice in ACTIONS:
                try:
                    ACTIONS[choice][1](client, cfg)
                except Exception as e:  # noqa: BLE001
                    print(ui.fail(f"Ошибка: {s3.friendly_error(e)}"))
            else:
                print(ui.warn("Нет такого пункта."))
            ui.pause()
    finally:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())