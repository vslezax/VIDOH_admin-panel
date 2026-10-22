"""
Снапшот БД (PostgreSQL/Neon) + S3-хранилища (Backblaze B2).

Что делает:
  Создаёт папку-снапшот вида  snapshots/2025-01-31_14-05-00/  с бэкапами:
    database/
        dump.sql            -- если найден pg_dump (наиболее полный формат)
        dump.json           -- всегда: полный фолбэк на psycopg2 (работает без pg_dump)
        manifest.json       -- таблицы, число строк, размеры
    s3/<bucket>/
        ...файлы...         -- побайтная копия объектов бакета
        manifest.json       -- ключи, размеры, etag
    snapshot.json           -- сводный манифест (дата, счётчики, суммы)
  Опционально пакуется в zip-архив.

Замечания:
  * pg_dump всё же предпочтительнее для схемы (DDL, последовательности,
    комментарии). Если его нет в PATH — используется только JSON-фолбэк
    (данные + DDL таблиц по information_schema).
  * Снапшот не восстанавливает данные автоматически — это холодная копия.

Запуск (интерактивно):
    python service/backup_snapshot.py

Запуск (аргументы):
    python service/backup_snapshot.py --label before-migration --zip
    python service/backup_snapshot.py --no-s3           # только БД
    python service/backup_snapshot.py --no-db           # только S3
    python service/backup_snapshot.py --bucket media    # конкретный бакет
    python service/backup_snapshot.py --list            # список снапшотов
    python service/backup_snapshot.py --out D:\\backups
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import shutil as _shutil
from lib import s3 as s3lib
from lib import ui

try:
    from lib import db as dblib
except Exception:  # noqa: BLE001 — модуль импортируется даже без psycopg2
    dblib = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "snapshots"


# --- Утилиты ----------------------------------------------------------------

def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _dump_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _human_size(num: int) -> str:
    return s3lib.human_size(num)


def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


# --- Источник БД ------------------------------------------------------------

def _find_pg_dump() -> str | None:
    exe = _shutil.which("pg_dump")
    if exe:
        return exe
    # типовые места установки PostgreSQL в Windows
    for base in (r"C:\Program Files\PostgreSQL", r"C:\Program Files (x86)\PostgreSQL"):
        basep = Path(base)
        if basep.exists():
            for ver in sorted(basep.iterdir(), reverse=True):
                cand = ver / "bin" / "pg_dump.exe"
                if cand.exists():
                    return str(cand)
    return None


def _db_url() -> str | None:
    if dblib is None:
        return None
    try:
        return dblib.get_database_url()
    except Exception:  # noqa: BLE001
        return None


def backup_db_pg_dump(url: str, dest: Path) -> dict[str, Any]:
    """Полный дамп через pg_dump (plain SQL). Возвращает метаданные."""
    pg_dump = _find_pg_dump()
    if not pg_dump:
        return {"ok": False, "error": "pg_dump не найден в PATH"}
    sql_path = dest / "dump.sql"
    cmd = [pg_dump, "--no-owner", "--no-privileges", "-f", str(sql_path), url]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or "").strip()[:500]}
    return {
        "ok": True,
        "method": "pg_dump",
        "file": sql_path.name,
        "bytes": sql_path.stat().st_size if sql_path.exists() else 0,
        "seconds": round(time.time() - t0, 2),
        "pg_dump": pg_dump,
    }


def _ddl_for_table(conn, table: str) -> list[str]:
    """Best-effort DDL (колонки + типы + дефолты + NOT NULL) по information_schema."""
    cols = dblib.table_columns(conn, table)
    parts: list[str] = []
    for c in cols:
        line = f'{dblib.quote_ident(c["column_name"])} {c["udt_name"]}'
        if c["is_nullable"] == "NO":
            line += " NOT NULL"
        if c["column_default"]:
            line += f' DEFAULT {c["column_default"]}'
        parts.append(line)
    ddl = f'CREATE TABLE IF NOT EXISTS {dblib.quote_ident(table)} (\n  ' + ",\n  ".join(parts) + "\n);"
    return [ddl]


def backup_db_json(dest: Path) -> dict[str, Any]:
    """Фолбэк без pg_dump: полные данные всех таблиц + примитивный DDL в JSON."""
    if dblib is None:
        return {"ok": False, "error": "модуль lib.db недоступен (нет psycopg2?)"}
    try:
        conn = dblib.connect()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"не удалось подключиться к БД: {e}"}

    t0 = time.time()
    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(sep=" "),
        "tables": {},
    }
    summary: list[dict[str, Any]] = []
    try:
        tables = dblib.list_tables(conn)
        for t in tables:
            rows = dblib.query(conn, f"SELECT * FROM {dblib.quote_ident(t)};")
            payload["tables"][t] = {
                "ddl": _ddl_for_table(conn, t),
                "rows": rows,
            }
            summary.append({"table": t, "rows": len(rows)})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    json_path = dest / "dump.json"
    _dump_json(json_path, payload)
    total_rows = sum(s["rows"] for s in summary)
    return {
        "ok": True,
        "method": "json",
        "file": json_path.name,
        "bytes": json_path.stat().st_size if json_path.exists() else 0,
        "seconds": round(time.time() - t0, 2),
        "tables": summary,
        "total_rows": total_rows,
    }


# --- Источник S3 ------------------------------------------------------------

def _s3_buckets(client, cfg) -> list[str]:
    try:
        buckets, _ = s3lib.accessible_buckets(client, cfg)
        return buckets
    except Exception:  # noqa: BLE001
        return [cfg.default_bucket] if cfg.default_bucket else []


def backup_s3(dest_root: Path, buckets: list[str] | None) -> dict[str, Any]:
    ok, reason = s3lib.is_configured()
    if not ok:
        return {"ok": False, "error": reason}

    cfg = s3lib.load_config()
    client = s3lib.make_client(cfg)

    targets = buckets or _s3_buckets(client, cfg)
    if not targets:
        return {"ok": False, "error": "нет доступных бакетов"}

    results: dict[str, Any] = {}
    total_bytes = 0
    total_objects = 0

    for bucket in targets:
        bdir = dest_root / bucket
        bdir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        objects: list[dict[str, Any]] = []

        try:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    local_path = bdir / key
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        client.download_file(bucket, key, str(local_path))
                    except Exception as e:  # noqa: BLE001
                        print(ui.fail(f"    ! {key}: {s3lib.friendly_error(e)}"))
                        continue
                    objects.append(
                        {
                            "key": key,
                            "size": obj["Size"],
                            "etag": obj.get("ETag", "").strip('"'),
                            "last_modified": obj["LastModified"].isoformat(sep=" "),
                        }
                    )
        except Exception as e:  # noqa: BLE001
            results[bucket] = {"ok": False, "error": s3lib.friendly_error(e)}
            continue

        b_bytes = sum(o["size"] for o in objects)
        total_bytes += b_bytes
        total_objects += len(objects)
        bucket_manifest = {
            "bucket": bucket,
            "objects": objects,
            "object_count": len(objects),
            "total_bytes": b_bytes,
            "seconds": round(time.time() - t0, 2),
        }
        _dump_json(bdir / "manifest.json", bucket_manifest)
        results[bucket] = {"ok": True, **bucket_manifest}

    return {
        "ok": all(r.get("ok") for r in results.values()) if results else False,
        "buckets": results,
        "total_objects": total_objects,
        "total_bytes": total_bytes,
    }


# --- Сборка снапшота --------------------------------------------------------

def make_snapshot(
    out_dir: Path,
    label: str | None = None,
    do_db: bool = True,
    do_s3: bool = True,
    buckets: list[str] | None = None,
    make_zip: bool = False,
) -> Path:
    stamp = _now_stamp()
    folder_name = f"{stamp}" + (f"_{label}" if label else "")
    snap_dir = out_dir / folder_name
    snap_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "created_at": datetime.now().isoformat(sep=" "),
        "label": label,
        "host": os.getenv("COMPUTERNAME") or os.uname().nodename if hasattr(os, "uname") else os.getenv("COMPUTERNAME", ""),
        "items": {},
    }

    # --- БД ---
    if do_db:
        db_dir = snap_dir / "database"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_info: dict[str, Any] = {"pg_dump": None, "json": None}

        url = _db_url()
        if url:
            print(ui.info("  [БД] пробую pg_dump…"))
            pg_res = backup_db_pg_dump(url, db_dir)
            db_info["pg_dump"] = pg_res
            if pg_res.get("ok"):
                print(ui.ok(f"  [БД] pg_dump OK: {db_dir / 'dump.sql'} ({_human_size(pg_res['bytes'])})"))
            else:
                print(ui.warn(f"  [БД] pg_dump недоступен: {pg_res.get('error')}"))
        else:
            print(ui.warn("  [БД] DATABASE_URL не найден в .env — пропускаю БД"))

        print(ui.info("  [БД] делаю JSON-фолбэк (полные данные всех таблиц)…"))
        json_res = backup_db_json(db_dir)
        db_info["json"] = json_res
        if json_res.get("ok"):
            print(ui.ok(
                f"  [БД] JSON OK: {json_res['total_rows']} строк, "
                f"{_human_size(json_res['bytes'])} за {json_res['seconds']}с"
            ))
        else:
            print(ui.fail(f"  [БД] JSON-фолбэк не удался: {json_res.get('error')}"))

        _dump_json(db_dir / "manifest.json", db_info)
        manifest["items"]["database"] = db_info

    # --- S3 ---
    if do_s3:
        s3_root = snap_dir / "s3"
        s3_root.mkdir(parents=True, exist_ok=True)
        print(ui.info("  [S3] копирую объекты…"))
        s3_res = backup_s3(s3_root, buckets)
        manifest["items"]["s3"] = s3_res
        if s3_res.get("ok"):
            print(ui.ok(
                f"  [S3] OK: {s3_res['total_objects']} объектов, "
                f"{_human_size(s3_res['total_bytes'])}"
            ))
        else:
            print(ui.fail(f"  [S3] ошибка: {s3_res.get('error')}"))

    # --- Сводный манифест ---
    _dump_json(snap_dir / "snapshot.json", manifest)

    size = _dir_size(snap_dir)
    manifest["snapshot_size_bytes"] = size
    _dump_json(snap_dir / "snapshot.json", manifest)

    print(ui.ok(f"\n  Снапшот готов: {snap_dir}"))
    print(ui.dim(f"  Размер папки: {_human_size(size)}"))

    # --- Zip ---
    if make_zip:
        zip_path = out_dir / f"{folder_name}.zip"
        print(ui.info(f"  Упаковываю в архив: {zip_path.name}…"))
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in snap_dir.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(out_dir))
        print(ui.ok(f"  Архив: {zip_path} ({_human_size(zip_path.stat().st_size)})"))

    return snap_dir


# --- Список снапшотов -------------------------------------------------------

def list_snapshots(out_dir: Path) -> None:
    ui.header(f"Снапшоты в {out_dir}")
    if not out_dir.exists():
        print(ui.dim("  Папка снапшотов не существует."))
        return
    items = sorted([p for p in out_dir.iterdir() if p.is_dir()], reverse=True)
    if not items:
        print(ui.dim("  Снапшотов нет."))
        return

    rows = []
    for p in items:
        manifest_file = p / "snapshot.json"
        info = {}
        if manifest_file.exists():
            try:
                info = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                info = {}
        size = _human_size(_dir_size(p))

        db_info = (info.get("items") or {}).get("database") or {}
        json_info = db_info.get("json") or {}
        rows_db = json_info.get("total_rows", "-")

        s3_info = (info.get("items") or {}).get("s3") or {}
        rows_s3 = s3_info.get("total_objects", "-")

        rows.append([p.name, size, rows_db, rows_s3])

    ui.print_table(
        ["снапшот", "размер", "строк БД", "объектов S3"],
        rows,
        max_width=50,
    )
    zipped = sorted([p.name for p in out_dir.iterdir() if p.suffix == ".zip"], reverse=True)
    if zipped:
        ui.section("Архивы")
        for z in zipped:
            print(f"  • {z}")


# --- CLI --------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Снапшот БД (Neon/PostgreSQL) и S3 (Backblaze B2).",
    )
    ap.add_argument("--label", help="метка в имени снапшота, напр. before-migration")
    ap.add_argument("--out", help=f"папка для снапшотов (по умолчанию {DEFAULT_OUT})")
    ap.add_argument("--no-db", action="store_true", help="не бэкапить БД")
    ap.add_argument("--no-s3", action="store_true", help="не бэкапить S3")
    ap.add_argument("--bucket", action="append", help="конкретный бакет (можно несколько)")
    ap.add_argument("--zip", action="store_true", help="упаковать снапшот в zip-архив")
    ap.add_argument("--list", action="store_true", help="показать ранее созданные снапшоты")
    return ap.parse_args(argv)


def _interactive(out_dir: Path) -> int:
    ui.header("BACKUP — снапшот БД + S3")
    label = ui.ask("Метка (необязательно)", default="") or None
    do_db = ui.ask("Бэкапить БД? (y/n)", default="y").lower() != "n"
    do_s3 = ui.ask("Бэкапить S3? (y/n)", default="y").lower() != "n"
    buckets = None
    if do_s3:
        raw = ui.ask("Бакеты через запятую (Enter — все доступные)", default="")
        if raw.strip():
            buckets = [b.strip() for b in raw.split(",") if b.strip()]
    make_zip = ui.ask("Упаковать в zip? (y/n)", default="n").lower() == "y"

    print()
    make_snapshot(
        out_dir=out_dir,
        label=label,
        do_db=do_db,
        do_s3=do_s3,
        buckets=buckets,
        make_zip=make_zip,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    out_dir = Path(args.out).resolve() if args.out else DEFAULT_OUT

    if args.list:
        list_snapshots(out_dir)
        return 0

    # Полностью без аргументов — интерактивный режим
    if argv is None and len(sys.argv) == 1:
        return _interactive(out_dir)

    if args.no_db and args.no_s3:
        print(ui.fail("Указаны --no-db и --no-s3 одновременно — нечего делать."))
        return 2

    try:
        make_snapshot(
            out_dir=out_dir,
            label=args.label,
            do_db=not args.no_db,
            do_s3=not args.no_s3,
            buckets=args.bucket,
            make_zip=args.zip,
        )
    except KeyboardInterrupt:
        print(ui.warn("\n  Прервано пользователем."))
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
