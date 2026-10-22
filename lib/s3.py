"""
Работа с S3-совместимым хранилищем (Backblaze B2) для консольных скриптов.

Клиент на boto3. Креды берутся из .env:
    S3_ENDPOINT_URL   — эндпоинт Backblaze, напр. https://s3.eu-central-003.backblazeb2.com
    S3_REGION         — регион из эндпоинта, напр. eu-central-003
    S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY  — Application Key ID / Application Key
    S3_BUCKET         — бакет по умолчанию

Важно: ключи Backblaze, ограниченные одним бакетом, НЕ имеют права listBuckets.
Поэтому функции, которым нужен список бакетов, используют fallback на S3_BUCKET.

Все функции «мягко» деградируют: если boto3/креды отсутствуют, возвращают
None и сообщение об ошибке, а не падают.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from . import ui

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class S3Config:
    endpoint_url: str | None
    region: str
    access_key: str | None
    secret_key: str | None
    default_bucket: str | None


def load_config() -> S3Config:
    load_dotenv(ROOT / ".env", override=True)
    return S3Config(
        endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        region=os.getenv("S3_REGION", "us-east-1"),
        access_key=os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID"),
        secret_key=os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"),
        default_bucket=os.getenv("S3_BUCKET") or None,
    )


def is_configured() -> tuple[bool, str]:
    """Проверяет, достаточно ли данных для подключения. Возвращает (ok, причина)."""
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False, "модуль boto3 не установлен (pip install boto3)"
    cfg = load_config()
    if not cfg.endpoint_url:
        return False, "не задан S3_ENDPOINT_URL в .env"
    if not cfg.access_key or not cfg.secret_key:
        return False, "не заданы S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY в .env"
    return True, "ok"


def make_client(cfg: S3Config | None = None):
    import boto3
    from botocore.config import Config

    cfg = cfg or load_config()
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint_url,
        region_name=cfg.region,
        aws_access_key_id=cfg.access_key,
        aws_secret_access_key=cfg.secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def friendly_error(exc: Exception) -> str:
    """Превращает ошибки boto3 в понятные подсказки для Backblaze."""
    msg = str(exc)
    code = ""
    try:
        code = exc.response.get("Error", {}).get("Code", "")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    if code == "InvalidAccessKeyId" or "Malformed Access Key Id" in msg:
        return (
            "неверный/неполный S3_ACCESS_KEY_ID (keyID). Скопируйте полностью, "
            "обычно ~25 символов, начинается с 00."
        )
    if code == "SignatureDoesNotMatch":
        return "неверный S3_SECRET_ACCESS_KEY (applicationKey)."
    if code == "AccessDenied" or "not entitled" in msg:
        return (
            "у ключа нет прав на эту операцию (например, listBuckets). "
            "Это нормально для ключа, ограниченного бакетом; работаем через S3_BUCKET."
        )
    if "NoSuchBucket" in msg:
        return "бакет не найден. Проверьте S3_BUCKET."
    if "Could not connect" in msg or "ConnectTimeout" in msg or "EndpointConnectionError" in msg:
        return "не удалось подключиться к эндпоинту. Проверьте S3_ENDPOINT_URL и интернет."
    return msg


def human_size(num: int | None) -> str:
    if num is None:
        return "-"
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < step:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= step
    return f"{num:.1f} PB"


def list_buckets(client) -> list[str]:
    """Список всех бакетов. Может бросить AccessDenied для ограниченных ключей."""
    resp = client.list_buckets()
    return [b["Name"] for b in resp.get("Buckets", [])]


def accessible_buckets(client, cfg: S3Config) -> tuple[list[str], str]:
    """
    Возвращает (список бакетов, источник).
    Если listBuckets запрещён — возвращает только S3_BUCKET из .env.
    """
    try:
        return list_buckets(client), "listBuckets"
    except Exception as e:  # noqa: BLE001
        if cfg.default_bucket:
            return [cfg.default_bucket], "fallback: S3_BUCKET"
        raise


def list_objects(client, bucket: str, prefix: str = "", limit: int = 1000) -> list[dict[str, Any]]:
    """Возвращает список объектов (возможно с пагинацией до limit)."""
    objects: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects.append(
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(sep=" "),
                    "storage_class": obj.get("StorageClass", ""),
                }
            )
            if len(objects) >= limit:
                return objects
    return objects


def build_public_url(cfg: S3Config, key: str) -> str:
    """
    Строит URL объекта.
    Для Backblaze с публичным бакетом объект доступен как
    https://<bucket>.s3.<region>.backblazeb2.com/<key>
    (используем bucket-style хост; при endpoint s3.<region>... заменяем поддомен).
    """
    if not cfg.endpoint_url:
        return key
    ep = cfg.endpoint_url.rstrip("/")
    if not cfg.default_bucket:
        return f"{ep}/{key}"
    # ep вида https://s3.<region>.backblazeb2.com -> https://<bucket>.s3.<region>.backblazeb2.com
    scheme, _, host = ep.partition("://")
    return f"{scheme}://{cfg.default_bucket}.{host}/{key}"


def media_type_from_mime(content_type: str) -> str:
    """Маппинг MIME -> media_type enum ('image' | 'video' | 'doc')."""
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    return "doc"


def print_not_configured(reason: str) -> None:
    print(ui.warn(f"  S3-хранилище не настроено: {reason}"))
    print(ui.dim("  Заполните в .env: S3_ENDPOINT_URL, S3_REGION, S3_ACCESS_KEY_ID,"))
    print(ui.dim("  S3_SECRET_ACCESS_KEY, S3_BUCKET"))


def verify() -> int:
    """Проверка конфигурации и связи с Backblaze. Возвращает код выхода."""
    ok, reason = is_configured()
    if not ok:
        print(ui.fail(f"Конфигурация S3 неполная: {reason}"))
        return 1
    cfg = load_config()
    print(ui.info(f"Эндпоинт: {cfg.endpoint_url}"))
    print(ui.info(f"Регион:   {cfg.region}"))
    print(ui.info(f"Бакет:    {cfg.default_bucket or '(не задан)'}"))

    client = make_client(cfg)
    # 1) Проверка доступа к конкретному бакету (главное)
    if cfg.default_bucket:
        try:
            client.head_bucket(Bucket=cfg.default_bucket)
            print(ui.ok(f"Доступ к бакету '{cfg.default_bucket}': OK"))
        except Exception as e:  # noqa: BLE001
            print(ui.fail(f"Нет доступа к бакету: {friendly_error(e)}"))
            return 1
    # 2) Пробуем список бакетов (не критично)
    try:
        buckets = list_buckets(client)
        print(ui.ok(f"listBuckets: доступен, бакетов: {len(buckets)}"))
        for b in buckets:
            mark = "  ← по умолчанию" if b == cfg.default_bucket else ""
            print(f"  • {b}{mark}")
    except Exception as e:  # noqa: BLE001
        print(ui.warn(f"listBuckets недоступен ({friendly_error(e)}) — это нормально для ограниченного ключа."))
    print(ui.ok("Подключение настроено корректно."))
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())