"""
Проверка зависимостей перед удалением записи.

Для таблицы-цели находит все FK из information_schema, которые ссылаются на неё,
и для конкретного значения PK считает зависимые строки. По правилу ON DELETE:
  - CASCADE   -> зависимые строки БУДУТ УДАЛЕНЫ;
  - SET NULL  -> поля будут ОБНУЛЕНЫ;
  - SET DEFAULT -> поля получат значение по умолчанию;
  - NO ACTION/RESTRICT -> удаление БУДЕТ ЗАБЛОКИРОВАНО.

Использование:
    deps = collect_dependencies(conn, 'media', pk_value=5)
    ok = report_dependencies(deps)   # печатает отчёт и возвращает False,
                                     # если есть блокирующие (RESTRICT) зависимости
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import db, ui


@dataclass
class Dependency:
    table: str
    column: str
    delete_rule: str
    count: int
    sample_pk: list[Any] = field(default_factory=list)


def _fk_map(conn, target_table: str) -> list[dict[str, Any]]:
    """Все FK, ссылающиеся на target_table."""
    sql = """
        SELECT
            tc.table_name        AS ref_table,
            kcu.column_name      AS ref_column,
            ccu.column_name      AS target_column,
            rc.delete_rule       AS delete_rule
        FROM information_schema.referential_constraints rc
        JOIN information_schema.table_constraints tc
             ON tc.constraint_name = rc.constraint_name
        JOIN information_schema.key_column_usage kcu
             ON kcu.constraint_name = rc.constraint_name
        JOIN information_schema.constraint_column_usage ccu
             ON ccu.constraint_name = rc.constraint_name
        WHERE ccu.table_name = %s
          AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name;
    """
    return db.query(conn, sql, (target_table,))


def collect_dependencies(conn, target_table: str, pk_value: Any) -> list[Dependency]:
    """Считает зависимые строки для записи target_table с PK = pk_value."""
    deps: list[Dependency] = []
    for fk in _fk_map(conn, target_table):
        ref_table = fk["ref_table"]
        ref_column = fk["ref_column"]
        target_column = fk["target_column"]
        rule = fk["delete_rule"]

        # Сколько строк ссылается на эту запись
        cnt_rows = db.query(
            conn,
            f"SELECT COUNT(*) AS c FROM {db.quote_ident(ref_table)} "
            f"WHERE {db.quote_ident(ref_column)} = %s;",
            (pk_value,),
        )
        count = int(cnt_rows[0]["c"])
        if count == 0:
            continue

        # Пара примеров PK зависимых строк (если у таблицы есть id)
        sample: list[Any] = []
        cols = [c["column_name"] for c in db.table_columns(conn, ref_table)]
        if "id" in cols:
            srows = db.query(
                conn,
                f"SELECT id FROM {db.quote_ident(ref_table)} "
                f"WHERE {db.quote_ident(ref_column)} = %s ORDER BY id LIMIT 5;",
                (pk_value,),
            )
            sample = [r["id"] for r in srows]

        deps.append(
            Dependency(
                table=ref_table,
                column=ref_column,
                delete_rule=rule,
                count=count,
                sample_pk=sample,
            )
        )
    return deps


def is_blocking(rule: str) -> bool:
    return rule in ("NO ACTION", "RESTRICT")


def report_dependencies(deps: list[Dependency]) -> bool:
    """
    Печатает отчёт о зависимостях. Возвращает False, если есть блокирующие
    (RESTRICT/NO ACTION) зависимости с ненулевым количеством строк.
    """
    if not deps:
        print(ui.ok("  Зависимых записей не найдено."))
        return True

    print(ui.warn("  Найдены зависимые записи:"))
    blocking = False
    for d in deps:
        if d.delete_rule == "CASCADE":
            effect = ui.fail("будут УДАЛЕНЫ (CASCADE)")
        elif d.delete_rule == "SET NULL":
            effect = ui.warn("поле будет ОБНУЛЕНО (SET NULL)")
        elif d.delete_rule == "SET DEFAULT":
            effect = ui.warn("поле получит DEFAULT (SET DEFAULT)")
        else:
            effect = ui.fail("удаление ЗАБЛОКИРОВАНО (RESTRICT/NO ACTION)")
            blocking = True
        sample = f"  напр. id={d.sample_pk}" if d.sample_pk else ""
        print(f"    - {d.table}.{d.column}: {d.count} стр. → {effect}{sample}")

    if blocking:
        print(ui.fail(
            "\n  Удаление невозможно: есть зависимые записи с правилом RESTRICT/NO ACTION.\n"
            "  Сначала удалите или переназначьте их."
        ))
    return not blocking