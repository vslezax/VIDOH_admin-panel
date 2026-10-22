
"""
Восстановление БД (PostgreSQL/Neon) и S3 (Backblaze B2) из снапшота,
созданного service/backup_snapshot.py.

Что умеет:
  * показать список снапшотов и выбрать нужный (интерактивно или --snapshot);
  * восстановить БД:
      - из dump.sql через psql (полная схема + данные), если файл есть
        и psql доступен;
      - из dump.json через psycopg2 (данные + DDL): очистка целевых
        таблиц, вставка в порядке, учитывающем FK, и правка
        identity-последовательностей (setval);
  * восстановить S3: загрузка всех объектов бакета из <snap>/s3/<bucket>/,
    опционально с очисткой бакета перед загрузкой.

ВАЖНО: операция деструктивна (перезаписывает/очищает данные). По умолчанию
LL треубет подтверждения ввода 'yes'.

Запуск:
    python service/restore_snapshot.py                    # интерактивно
    python service/restore_snapshot.py --list            # список снапшотов
    python service/restore_snapshot.py --snapshot <path|name>
    python service/restore_snapshot.py --snapshot <name> --db-only
    python service/restore_snapshot.py --snapshot <name> --s3-only
    python service/restore_snapshot.py --snapshot <name> --prefer-sql
    python service/restore_snapshot.py --snapshot <name> --clean-s3
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), r".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from lib import s3 as s3lib
from lib import ui

try:
    from lib import db as dblib
except Exception:  # noqa: BLE001
    dblib = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "snapshots"


# --- Поиск снапшота ---------------------------------------------------------

def find_snapshot(arg: str | None, out_dir: Path) -> Path | None:
    """Аргумент может быть путём к папке/zip или именем относительно out_dir."""
    if arg:
        p = Path(arg)
        if p.is_dir() and (p / "snapshot.json").exists():
            return p
        cand = out_dir / arg
        if cand.is_dir():
            return cand
        # возможно, указан zip
        zc = out_dir / (arg if arg.endswith(".zip") else arg + ".zip")
        if zc.exists():
            return zc
        return None

    items = sorted([p for p in out_dir.iterdir() if p.is_dir()], reverse=True) if out_dir.exists() else []
    if not items:
        return None
    ui.section("Доступные снапшоты")
    for i, p in enumerate(items, 1):
        print(f"  {i:2}. {p.name}")
    choice = ui.ask_int("Номер снапшота (Enter — самый свежий)")
    if choice is None:
        return items[0]
    if 1 <= choice <= len(items):
        return items[choice - 1]
    print(ui.fail("  Нет такого снапшота."))
    return None


def prepare_snapshot_dir(snap: Path, work_dir: Path) -> Path:
    """Если снапшот — zip, распаковывает во временную папку и возвращает её."""
    if snap.suffix == ".zip":
        import zipfile

        target = work_dir / snap.stem
        target.mkdir(parents=True, exist_ok=True)
        ui.info(f"  Распаковываю архив {snap.name} → {target}")
        with zipfile.ZipFile(snap, "r") as zf:
            zf.extractall(target)
        # zip может содержать один корневой каталог
        entries = [p for p in target.iterdir()]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return target
    return snap


# --- Восстановление БД ------------------------------------------------------

def _find_psql() -> str | None:
    exe = shutil.which("psql")
    if exe:
        return exe
    for base in (r"C:\Program Files\PostgreSQL", r"C:\Program Files (x86)\PostgreSQL"):
        bp = Path(base)
        if bp.exists():
            for ver in sorted(bp.iterdir(), reverse=True):
                cand = ver / "bin" / "psql.exe"
                if cand.exists():
                    return str(cand)
    return None


def restore_db_from_sql(sql_path: Path) -> bool:
    """Запускает psql -f dump.sql. dump.sql обычно содержит CREATE DATABASE-независимую схему."""
    psql = _find_psql()
    if not psql:
        print(ui.fail("  psql не найден в PATH — восстановление из SQL невозможно."))
        return False
    if dblib is None:
        print(ui.fail("  модуль lib.db недоступен."))
        return False
    try:
        url = dblib.get_database_url()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  DATABASE_URL: {e}"))
        return False

    print(ui.info(f"  psql -f {sql_path.name} …"))
    cmd = [psql, url, "-v", "ON_ERROR_STOP=1", "-f", str(sql_path)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(ui.fail(f"  psql ошибка: {(proc.stderr or '').strip()[:600]}"))
        return False
    print(ui.ok(f"  SQL восстановлен за {round(time.time() - t0, 2)}с"))
    return True


def _fk_order(conn, tables: list[str]) -> list[str]:
    """
    Топологическая сортировка таблиц по FK, чтобы вставлять «родителей» раньше.
    Таблицы без связей / циклы обрабатываются как есть.
    """
    # graph: table -> set of referenced tables (parents)
    parents: dict[str, set[str]] = {t: set() for t in tables}
    fks = dblib.query(
        conn,
        """
        SELECT tc.table_name AS child, ccu.table_name AS parent
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
        """,
    )
    for fk in fks:
        child, parent = fk["child"], fk["parent"]
        if child in parents and parent in parents and child != parent:
            parents[child].add(parent)

    ordered: list[str] = []
    visited: set[str] = set()
    temp: set[str] = set()

    def visit(t: str) -> None:
        if t in visited:
            return
        if t in temp:  # цикл — вставляем как есть
            return
        temp.add(t)
        for p in parents[t]:
            visit(p)
        temp.discard(t)
        visited.add(t)
        ordered.append(t)

    for t in tables:
        visit(t)
    return ordered


def _identity_columns(conn, table: str) -> list[dict[str, Any]]:
    return dblib.query(
        conn,
        """
        SELECT column_name, is_identity
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position;
        """,
        (table,),
    )


def _reset_sequences(conn) -> list[str]:
    """setval для всех identity/serial-последовательностей по max(id)."""
    fixed: list[str] = []
    seqs = dblib.query(
        conn,
        """
        SELECT
            n.nspname || '.' || c.relname AS sequence,
            t.relname AS table_name,
            a.attname AS column_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_depend dep ON dep.objid = c.oid
        JOIN pg_class t ON t.oid = dep.refobjid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = dep.refobjsubid
        WHERE c.relkind = 'S' AND n.nspname = 'public';
        """,
    )
    for s in seqs:
        seq = s["sequence"]
        table = s["table_name"]
        col = s["column_name"]
        try:
            maxrow = dblib.query(
                conn,
                f"SELECT COALESCE(MAX({dblib.quote_ident(col)}), 0) AS m FROM {dblib.quote_ident(table)};",
            )
            maxv = int(maxrow[0]["m"])
            # если таблица пустая — nextval вернёт 1 (или стартовое значение)
            if maxv > 0:
                dblib.execute(conn, f"SELECT setval(%s, %s);", (seq, maxv))
            else:
                dblib.execute(conn, f"SELECT setval(%s, 1, false);", (seq,))
            fixed.append(f"{table}.{col} -> {maxv}")
        except Exception as e:  # noqa: BLE001
            print(ui.warn(f"  setval {seq}: {e}"))
    return fixed


def restore_db_from_json(dest: Path) -> bool:
    """Полное восстановление из dump.json: очистка, вставка по FK-порядку, setval."""
    if dblib is None:
        print(ui.fail("  модуль lib.db недоступен (нет psycopg2?)."))
        return False
    json_path = dest / "dump.json"
    if not json_path.exists():
        print(ui.fail(f"  Файл не найден: {json_path}"))
        return False

    data = json.loads(json_path.read_text(encoding="utf-8"))
    tables_data = data.get("tables") or {}

    try:
        conn = dblib.connect()
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Не удалось подключиться к БД: {e}"))
        return False

    try:
        existing = set(dblib.list_tables(conn))
        target = [t for t in tables_data.keys() if t in existing]
        if not target:
            print(ui.fail("  В БД нет таблиц из снапшота. Сначала разверните схему (deploy_schema.py)."))
            return False

        missing = [t for t in tables_data.keys() if t not in existing]
        if missing:
            print(ui.warn(f"  Таблиц из снапшота нет в БД (пропущены): {', '.join(missing)}"))

        # очистка
        print(ui.info("  Очищаю данные целевых таблиц (TRUNCATE ... CASCADE)…"))
        truncate_list = ", ".join(dblib.quote_ident(t) for t in target)
        dblib.execute(conn, f"TRUNCATE {truncate_list} RESTART IDENTITY CASCADE;")

        # порядок вставки
        order = _fk_order(conn, target)

        total = 0
        t0 = time.time()
        for t in order:
            payload = tables_data[t]
            rows = payload.get("rows") or []
            if not rows:
                print(ui.dim(f"  {t}: 0 строк"))
                continue
            cols = list(rows[0].keys())
            cols_sql = ", ".join(dblib.quote_ident(c) for c in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO {dblib.quote_ident(t)} ({cols_sql}) VALUES ({placeholders});"
            # параметризованная пакетная вставка
            with conn.cursor() as cur:
                for r in rows:
                    cur.execute(sql, [r.get(c) for c in cols])
            total += len(rows)
            print(ui.ok(f"  {t}: {len(rows)} строк"))

        fixed = _reset_sequences(conn)
        if fixed:
            print(ui.dim("  Последовательности сброшены:"))
            for f in fixed:
                print(ui.dim(f"    {f}"))

        print(ui.ok(f"  Данные восстановлены: {total} строк за {round(time.time() - t0, 2)}с"))
        return True
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка восстановления: {e}"))
        return False
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def restore_db(snap_dir: Path, prefer_sql: bool, force_json: bool) -> bool:
    db_dir = snap_dir / "database"
    if not db_dir.exists():
        print(ui.fail("  В снапшоте нет папки database/."))
        return False

    sql_path = db_dir / "dump.sql"
    json_path = db_dir / "dump.json"

    if prefer_sql and sql_path.exists() and not force_json:
        print(ui.info("  Режим: dump.sql (psql)"))
        if restore_db_from_sql(sql_path):
            return True
        print(ui.warn("  SQL-восстановление не удалось, пробую JSON..."))

    if json_path.exists():
        print(ui.info("  Режим: dump.json (psycopg2)"))
        return restore_db_from_json(db_dir)

    if sql_path.exists():
        print(ui.warn("  dump.json отсутствует, использую dump.sql"))
        return restore_db_from_sql(sql_path)

    print(ui.fail("  В снапшоте нет ни dump.sql, ни dump.json."))
    return False


# --- Восстановление S3 ------------------------------------------------------

def _empty_bucket(client, bucket: str) -> int:
    """Удаляет все объекты бакета. Возвращает число удалённых."""
    deleted = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if not objs:
            continue
        # удаляем пачками по 1000
        resp = client.delete_objects(Bucket=bucket, Delete={"Objects": objs})
        deleted += len(resp.get("Deleted", []))
    return deleted


def restore_s3(snap_dir: Path, buckets: list[str] | None, clean: bool) -> bool:
    s3_dir = snap_dir / "s3"
    if not s3_dir.exists():
        print(ui.fail("  В снапшоте нет папки s3/."))
        return False

    ok, reason = s3lib.is_configured()
    if not ok:
        print(ui.fail(f"  S3 не настроен: {reason}"))
        return False
    cfg = s3lib.load_config()
    client = s3lib.make_client(cfg)

    available = [p.name for p in s3_dir.iterdir() if p.is_dir()]
    targets = buckets or available
    if not targets:
        print(ui.fail("  В снапшоте нет данных S3."))
        return False

    all_ok = True
    for bucket in targets:
        bdir = s3_dir / bucket
        if not bdir.exists():
            print(ui.warn(f"  Бакет '{bucket}' отсутствует в снапшоте, пропускаю."))
            all_ok = False
            continue

        # убедимся, что бакет существует (создадим при необходимости)
        try:
            client.head_bucket(Bucket=bucket)
        except Exception as e:  # noqa: BLE001
            print(ui.warn(f"  Бакета '{bucket}' нет: {s3lib.friendly_error(e)}"))
            print(ui.info(f"  Создаю бакет '{bucket}'…"))
            try:
                client.create_bucket(Bucket=bucket)
            except Exception as e2:  # noqa: BLE001
                print(ui.fail(f"  Не удалось создать бакет: {s3lib.friendly_error(e2)}"))
                all_ok = False
                continue

        if clean:
            print(ui.info(f"  Очищаю бакет '{bucket}'…"))
            try:
                n = _empty_bucket(client, bucket)
                print(ui.ok(f"  Удалено объектов: {n}"))
            except Exception as e:  # noqa: BLE001
                print(ui.fail(f"  Ошибка очистки: {s3lib.friendly_error(e)}"))
                all_ok = False
                continue

        files = [
            p for p in bdir.rglob("*")
            if p.is_file() and p.name != "manifest.json"
        ]
        print(ui.info(f"  Загружаю {len(files)} объектов в '{bucket}'…"))
        uploaded = 0
        failed = 0
        for fp in files:
            key = fp.relative_to(bdir).as_posix()
            try:
                client.upload_file(str(fp), bucket, key)
                uploaded += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(ui.fail(f"    {key}: {s3lib.friendly_error(e)}"))
        print(ui.ok(f"  '{bucket}': загружено {uploaded}" + (f", ошибок {failed}" if failed else "")))
        if failed:
            all_ok = False

    return all_ok


# --- CLI --------------------------------------------------------------------

def _parse_args(argv: list[str]) -> Any:
    import argparse

    ap = argparse.ArgumentParser(
        description="Восстановление БД и S3 из снапшота.",
    )
    ap.add_argument("--snapshot", help="путь или имя снапшота (по умолчанию — интерактивно)")
    ap.add_argument("--out", help=f"папка со снапшотами (по умолчанию {DEFAULT_OUT})")
    ap.add_argument("--list", action="store_true", help="показать снапшоты и выйти")
    ap.add_argument("--db-only", action="store_true", help="только БД")
    ap.add_argument("--s3-only", action="store_true", help="только S3")
    ap.add_argument("--prefer-sql", action="store_true", help="восстанавливать БД из dump.sql (через psql)")
    ap.add_argument("--force-json", action="store_true", help="восстанавливать БД из dump.json, игнорируя dump.sql")
    ap.add_argument("--clean-s3", action="store_true", help="очистить бакет перед загрузкой объектов")
    ap.add_argument("--bucket", action="append", help="конкретный бакет (можно несколько)")
    ap.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")
    return ap.parse_args(argv)


def list_snapshots(out_dir: Path) -> None:
    ui.header(f"Снапшоты в {out_dir}")
    if not out_dir.exists():
        print(ui.dim("  Папка снапшотов не существует."))
        return
    items = sorted([p for p in out_dir.iterdir() if p.is_dir()], reverse=True)
    zips = sorted([p for p in out_dir.iterdir() if p.suffix == ".zip"], reverse=True)
    if not items and not zips:
        print(ui.dim("  Снапшотов нет."))
        return
    for p in items:
        print(f"  • {p.name}")
    for z in zips:
        print(f"  • {z.name} (архив)")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    out_dir = Path(args.out).resolve() if args.out else DEFAULT_OUT

    if args.list:
        list_snapshots(out_dir)
        return 0

    ui.header("RESTORE — восстановление из снапшота")

    snap = find_snapshot(args.snapshot, out_dir)
    if snap is None:
        print(ui.fail("  Снапшот не найден."))
        return 1

    # какие части восстанавливать
    do_db = not args.s3_only
    do_s3 = not args.db_only
    if args.db_only and args.s3_only:
        print(ui.fail("Указаны --db-only и --s3-only одновременно."))
        return 2

    print(ui.info(f"  Снапшот: {snap}"))

    # работаем с zip через распаковку
    tmp_dir = ROOT / ".restore_tmp"
    work_dir = prepare_snapshot_dir(snap, tmp_dir)

    try:
        # предупреждение и подтверждение
        print(ui.warn("\n  ВНИМАНИЕ: восстановление перезапишет текущие данные!"))
        if do_db:
            print(ui.warn("    • БД: таблицы из снапшота будут очищены и заполнены заново"))
        if do_s3:
            msg = "    • S3: объекты будут загружены"
            if args.clean_s3:
                msg += " (бакет предварительно ОЧИЩЕН)"
            print(ui.warn(msg))

        if not args.yes:
            if not ui.confirm("Продолжить восстановление?"):
                print(ui.dim("  Отменено."))
                return 0

        results: dict[str, bool] = {}

        if do_db:
            ui.section("Восстановление БД")
            results["db"] = restore_db(work_dir, args.prefer_sql, args.force_json)

        if do_s3:
            ui.section("Восстановление S3")
            results["s3"] = restore_s3(work_dir, args.bucket, args.clean_s3)

        ui.section("Итог")
        for k, ok in results.items():
            print((ui.ok(f"  {k}: OK") if ok else ui.fail(f"  {k}: ОШИБКА")))

        return 0 if all(results.values()) else 1
    finally:
        # чистим временную распаковку
        if tmp_dir.exists():
            try:
                shutil.rmtree(tmp_dir)
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    sys.exit(main())
