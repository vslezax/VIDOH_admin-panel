"""
Загрузка медиафайла в S3 (Backblaze B2) и регистрация в БД.

Интерактивный консольный скрипт:
  1. принимает путь к локальному файлу;
  2. определяет тип/размер (для изображений — width/height через Pillow);
  3. генерирует уникальный ключ и загружает файл в бакет;
  4. записывает строку в таблицу media (url, type, size_bytes, ...);
  5. при ошибке вставки в БД — удаляет уже загруженный объект из S3 (откат).

Запуск:  python upload_media.py
"""
from __future__ import annotations

import os
import sys
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r'..'))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import mimetypes
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from lib import db, s3, ui

ALLOWED_DEFAULT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".mov", ".webm"}


def _file_info(path: Path) -> dict:
    """Собирает сведения о файле: mime, размер, размеры изображения."""
    content_type, _ = mimetypes.guess_type(str(path))
    content_type = content_type or "application/octet-stream"
    info = {
        "name": path.name,
        "size": path.stat().st_size,
        "content_type": content_type,
        "width": None,
        "height": None,
    }
    if content_type.startswith("image/") and path.suffix.lower() != ".svg":
        try:
            from PIL import Image  # type: ignore
            with Image.open(path) as im:
                info["width"], info["height"] = im.size
        except Exception:  # noqa: BLE001
            info["width"] = info["height"] = None
    return info


def _make_storage_key(filename: str) -> str:
    now = datetime.now(timezone.utc)
    ext = Path(filename).suffix.lower()
    return f"media/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{ext}"


def _normalize_custom_dir(raw: str) -> str | None:
    """
    Нормализует пользовательский путь-префикс в каталог внутри бакета.
    - убирает ведущие '/', обратные слэши -> '/';
    - убирает пустые и '..'-сегменты (защита от выхода за пределы префикса);
    - гарантирует завершающий '/';
    Возвращает None, если после нормализации ничего не осталось.
    """
    parts = []
    for seg in raw.replace("\\", "/").split("/"):
        seg = seg.strip()
        if seg in ("", ".", ".."):
            continue
        parts.append(seg)
    if not parts:
        return None
    return "/".join(parts).strip("/") + "/"


def _make_custom_storage_key(custom_dir: str, filename: str) -> str:
    """Уникальный ключ в заданном каталоге: <custom_dir>/<uuid><ext>."""
    ext = Path(filename).suffix.lower()
    return f"{custom_dir}{uuid.uuid4().hex}{ext}"


def _check_user_exists(conn, user_id: int) -> bool:
    rows = db.query(conn, "SELECT 1 FROM users WHERE id=%s;", (user_id,))
    return bool(rows)


def upload(conn, client, cfg) -> None:
    ui.header("Загрузка файла в S3 + запись в media")

    # 1. Путь к файлу
    raw = ui.ask("Путь к локальному файлу")
    if not raw:
        print(ui.dim("  Отменено."))
        return
    path = Path(raw).expanduser()
    if not path.is_file():
        print(ui.fail(f"  Файл не найден: {path}"))
        return

    ext = path.suffix.lower()
    if ext not in ALLOWED_DEFAULT:
        print(ui.fail(f"  Недопустимое расширение '{ext}'. Разрешены только image/video."))
        return

    info = _file_info(path)
    ui.section("Параметры файла")
    print(f"  имя:        {info['name']}")
    print(f"  размер:     {s3.human_size(info['size'])} ({info['size']} B)")
    print(f"  mime:       {info['content_type']}")
    if info["width"] and info["height"]:
        print(f"  разрешение: {info['width']}x{info['height']}")

    default_type = s3.media_type_from_mime(info["content_type"])
    if default_type is None:
        print(ui.fail(f"  MIME '{info['content_type']}' не относится к image/video (media_type)."))
        return

    # 2. Доп. поля
    alt = ui.ask("alt-текст (описание), Enter — пусто", default="") or None
    type_in = ui.ask("Тип (image/video)", default=default_type).strip().lower()
    if type_in not in ("image", "video"):
        print(ui.warn(f"  Неверный тип '{type_in}', использую '{default_type}'."))
        type_in = default_type

    uploaded_by = None
    uid_raw = ui.ask("ID пользователя (uploaded_by), Enter — пусто", default="")
    if uid_raw:
        if uid_raw.isdigit() and _check_user_exists(conn, int(uid_raw)):
            uploaded_by = int(uid_raw)
        else:
            print(ui.warn(f"  Пользователь id={uid_raw} не найден — поле останется пустым."))

    # Каталог хранения: стандартный (media/YYYY/MM/) или пользовательский
    custom_dir = None
    if ui.confirm("Загрузить в свой каталог (вместо media/YYYY/MM/)?"):
        while True:
            raw_dir = ui.ask("Путь-префикс внутри бакета (напр. events/2025/avatars)")
            if not raw_dir:
                print(ui.dim("  Пустой путь — использую стандартный каталог."))
                break
            custom_dir = _normalize_custom_dir(raw_dir)
            if custom_dir is None:
                print(ui.warn("  Некорректный путь — попробуйте ещё раз."))
                continue
            print(ui.ok(f"  Каталог: {custom_dir}"))
            break

    if custom_dir:
        key = _make_custom_storage_key(custom_dir, info["name"])
    else:
        key = _make_storage_key(info["name"])
    url = s3.build_public_url(cfg, key)

    ui.section("Итог перед загрузкой")
    print(f"  бакет:       {cfg.default_bucket}")
    print(f"  ключ:        {key}")
    print(f"  url:         {url}")
    print(f"  тип:         {type_in}")

    if not ui.confirm("Загрузить файл в S3 и добавить запись в БД?"):
        print(ui.dim("  Отменено."))
        return

    # 3. Загрузка в S3
    try:
        client.upload_file(
            str(path),
            cfg.default_bucket,
            key,
            ExtraArgs={"ContentType": info["content_type"]},
        )
        print(ui.ok("  Файл загружен в S3."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка загрузки в S3: {s3.friendly_error(e)}"))
        return

    # 4. Запись в БД (с откатом S3 при ошибке)
    try:
        rows = db.query(
            conn,
            """
            INSERT INTO media
                (storage_key, url, type, alt, width, height, size_bytes, uploaded_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            RETURNING id;
            """,
            (key, url, type_in, alt, info["width"], info["height"], info["size"], uploaded_by),
        )
        new_id = rows[0]["id"] if rows else "?"
        print(ui.ok(f"  Запись в media создана: id={new_id}"))
        print(ui.ok("Готово."))
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка вставки в БД: {e}"))
        print(ui.warn("  Откатываю загрузку — удаляю объект из S3..."))
        try:
            client.delete_object(Bucket=cfg.default_bucket, Key=key)
            print(ui.ok("  Объект удалён из S3."))
        except Exception as e2:  # noqa: BLE001
            print(ui.fail(f"  Не удалось удалить объект из S3: {e2}"))


def main() -> int:
    # Проверка S3
    ok, reason = s3.is_configured()
    if not ok:
        ui.header("UPLOAD MEDIA")
        s3.print_not_configured(reason)
        return 1

    cfg = s3.load_config()
    if not cfg.default_bucket:
        print(ui.fail("Не задан S3_BUCKET в .env."))
        return 1

    # Проверка БД
    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Не удалось подключиться к БД: {e}"))
        return 1

    client = s3.make_client(cfg)
    try:
        client.head_bucket(Bucket=cfg.default_bucket)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Нет доступа к бакету '{cfg.default_bucket}': {s3.friendly_error(e)}"))
        conn.close()
        return 1

    try:
        upload(conn, client, cfg)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"Ошибка: {e}"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())