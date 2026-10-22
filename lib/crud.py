"""
Переиспользуемые хелперы для CRUD-скриптов админ-панели.

Собраны типовые операции, которые иначе дублировались бы в каждом
create_*/edit_*/delete_* скрипте:
  - ввод и валидация полей (текст, число, enum, bool, дата/время, FK);
  - выполнение INSERT/UPDATE с показом «было → станет» и подтверждением;
  - пагинированный просмотр таблицы с выбором строки по id.

Все функции используют интерактивный ввод через lib.ui и работают с
соединением psycopg2 (lib.db).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, Sequence

from . import db, ui


# --- Ввод значений ----------------------------------------------------------

NULL_TOKENS = ("null", "-", "none", "пусто")


def ask_text(prompt: str, current: Any = None, required: bool = False) -> tuple[bool, Any]:
    """
    Ввод текстового значения.
    Возвращает (changed, value). Пустой ввод = без изменений (если не required).
    Значения NULL_TOKENS -> None.
    """
    shown = "пусто" if current is None else current
    raw = ui.ask(f"{prompt} (текущее: {shown}), Enter — оставить")
    if raw == "":
        if required and current is None:
            print(ui.warn("  Обязательное поле, нужен ввод."))
            return ask_text(prompt, current, required)
        return False, current
    if raw.strip().lower() in NULL_TOKENS:
        return True, None
    return True, raw


def ask_int(
    prompt: str,
    current: Any = None,
    required: bool = False,
    min_value: int | None = None,
    max_value: int | None = None,
) -> tuple[bool, Any]:
    """Ввод целого значения с проверкой границ."""
    shown = "пусто" if current is None else current
    raw = ui.ask(f"{prompt} (текущее: {shown}), Enter — оставить")
    if raw == "":
        if required and current is None:
            print(ui.warn("  Обязательное поле, нужен ввод."))
            return ask_int(prompt, current, required, min_value, max_value)
        return False, current
    if raw.strip().lower() in NULL_TOKENS:
        return True, None
    try:
        val = int(raw)
    except ValueError:
        print(ui.fail("  Ожидалось целое число."))
        return ask_int(prompt, current, required, min_value, max_value)
    if min_value is not None and val < min_value:
        print(ui.fail(f"  Значение должно быть >= {min_value}."))
        return ask_int(prompt, current, required, min_value, max_value)
    if max_value is not None and val > max_value:
        print(ui.fail(f"  Значение должно быть <= {max_value}."))
        return ask_int(prompt, current, required, min_value, max_value)
    return True, val


def ask_decimal(prompt: str, current: Any = None, required: bool = False) -> tuple[bool, Any]:
    """Ввод десятичного числа (numeric)."""
    shown = "пусто" if current is None else current
    raw = ui.ask(f"{prompt} (текущее: {shown}), Enter — оставить")
    if raw == "":
        if required and current is None:
            print(ui.warn("  Обязательное поле, нужен ввод."))
            return ask_decimal(prompt, current, required)
        return False, current
    if raw.strip().lower() in NULL_TOKENS:
        return True, None
    try:
        return True, float(raw.replace(",", "."))
    except ValueError:
        print(ui.fail("  Ожидалось число."))
        return ask_decimal(prompt, current, required)


def ask_bool(prompt: str, current: Any = None) -> tuple[bool, bool]:
    """Ввод bool (y/n)."""
    shown = "да" if current else "нет" if current is not None else "пусто"
    raw = ui.ask(f"{prompt} (текущее: {shown}) [y/n], Enter — оставить")
    if raw == "":
        return False, bool(current)
    return True, raw.strip().lower() in ("y", "yes", "да", "1", "true")


def ask_enum(prompt: str, allowed: Sequence[str], current: Any = None) -> tuple[bool, Any]:
    """Ввод значения из enum-набора."""
    shown = current if current is not None else "пусто"
    raw = ui.ask(f"{prompt} /{'|'.join(allowed)}/ (текущее: {shown}), Enter — оставить")
    if raw == "":
        return False, current
    val = raw.strip().lower()
    if val not in allowed:
        print(ui.fail(f"  Недопустимое значение. Разрешено: {', '.join(allowed)}"))
        return ask_enum(prompt, allowed, current)
    return True, val


def ask_datetime(prompt: str, current: Any = None) -> tuple[bool, Any]:
    """
    Ввод даты/времени. Формат: YYYY-MM-DD HH:MM[:SS] или YYYY-MM-DD.
    Пусто -> без изменений; 'null' -> None.
    Возвращает строку для передачи в psycopg2 (TIMESTAMPTZ принимает ISO).
    """
    shown = current if current is not None else "пусто"
    raw = ui.ask(f"{prompt} (текущее: {shown}) [YYYY-MM-DD HH:MM], Enter — оставить")
    if raw == "":
        return False, current
    if raw.strip().lower() in NULL_TOKENS:
        return True, None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return True, dt.isoformat(sep=" ")
        except ValueError:
            continue
    print(ui.fail("  Неверный формат даты/времени."))
    return ask_datetime(prompt, current)


def ask_fk(
    conn,
    prompt: str,
    ref_table: str,
    current: Any = None,
    label_cols: Sequence[str] = ("id",),
    allow_null: bool = True,
) -> tuple[bool, Any]:
    """
    Ввод FK: ID ссылающейся записи с проверкой существования.
    Показывает до 10 записей-кандидатов (label_cols) для ориентира.
    """
    shown = "пусто" if current is None else current
    raw = ui.ask(f"{prompt} — ID из {ref_table} (текущее: {shown}), Enter — оставить")
    if raw == "":
        return False, current
    if allow_null and raw.strip().lower() in NULL_TOKENS:
        return True, None
    if not raw.strip().isdigit():
        print(ui.fail("  Ожидался числовой ID."))
        return ask_fk(conn, prompt, ref_table, current, label_cols, allow_null)
    val = int(raw)
    cols_sql = ", ".join(db.quote_ident(c) for c in label_cols)
    exists = db.query(
        conn, f"SELECT {cols_sql} FROM {db.quote_ident(ref_table)} WHERE id=%s;", (val,)
    )
    if not exists:
        # подсказка: показать несколько существующих
        sample = db.query(
            conn,
            f"SELECT id, {cols_sql} FROM {db.quote_ident(ref_table)} ORDER BY id LIMIT 10;",
        )
        if sample:
            print(ui.warn(f"  {ref_table} id={val} не найден. Доступные:"))
            ui.print_table(["id", *label_cols], [[r["id"], *[r[c] for c in label_cols]] for r in sample], max_width=30)
        else:
            print(ui.warn(f"  {ref_table} пуст."))
        if allow_null and ui.confirm("Оставить пусто?"):
            return True, None
        return ask_fk(conn, prompt, ref_table, current, label_cols, allow_null)
    return True, val


# --- Выполнение INSERT / UPDATE ---------------------------------------------

def show_diff(mapping: dict[str, Any], before: dict[str, Any] | None = None) -> None:
    """Печатает таблицу поле → было → станет."""
    if before is None:
        ui.print_table(["поле", "значение"], [[k, v] for k, v in mapping.items()], max_width=60)
    else:
        rows = [[k, f"{before.get(k)} → {v}"] for k, v in mapping.items()]
        ui.print_table(["поле", "было → станет"], rows, max_width=60)


def run_insert(conn, table: str, data: dict[str, Any], returning: str = "id") -> Any | None:
    """INSERT строки в table. Возвращает значение returning или None при ошибке."""
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    cols_sql = ", ".join(db.quote_ident(c) for c in cols)
    sql = f"INSERT INTO {db.quote_ident(table)} ({cols_sql}) VALUES ({placeholders}) RETURNING {returning};"
    try:
        rows = db.query(conn, sql, tuple(data.values()))
        return rows[0][returning] if rows else None
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка вставки: {e}"))
        return None


def run_update(conn, table: str, pk: Any, data: dict[str, Any], pk_col: str = "id") -> int:
    """UPDATE строки table по pk. Возвращает число обновлённых строк."""
    set_clause = ", ".join(f"{db.quote_ident(k)} = %s" for k in data)
    params = list(data.values()) + [pk]
    sql = f"UPDATE {db.quote_ident(table)} SET {set_clause} WHERE {db.quote_ident(pk_col)}=%s;"
    try:
        return db.execute(conn, sql, params)
    except Exception as e:  # noqa: BLE001
        print(ui.fail(f"  Ошибка обновления: {e}"))
        return 0


# --- Просмотр таблицы с выбором строки --------------------------------------

def list_rows(
    conn,
    table: str,
    columns: Sequence[str] | None = None,
    where: str = "",
    params: Sequence[Any] | None = None,
    order: str = "id DESC",
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Возвращает строки таблицы для отображения в списке."""
    cols = ", ".join(db.quote_ident(c) for c in columns) if columns else "*"
    sql = f"SELECT {cols} FROM {db.quote_ident(table)}"
    if where:
        sql += f" WHERE {where}"
    sql += f" ORDER BY {order} LIMIT %s;"
    p = list(params or []) + [limit]
    return db.query(conn, sql, p)


def print_rows(rows: Iterable[dict[str, Any]], columns: Sequence[str] | None = None, max_width: int = 32) -> None:
    rows = list(rows)
    if not rows:
        print(ui.dim("  (нет записей)"))
        return
    cols = list(columns) if columns else list(rows[0].keys())
    ui.print_table(cols, [[r.get(c) for c in cols] for r in rows], max_width=max_width)


def pick_id(conn, table: str) -> int | None:
    """Спрашивает id записи в table; проверяет существование."""
    raw = ui.ask_int(f"ID записи в {table}")
    if raw is None:
        return None
    found = db.query(conn, f"SELECT 1 FROM {db.quote_ident(table)} WHERE id=%s;", (raw,))
    if not found:
        print(ui.fail(f"  {table} id={raw} не найден."))
        return None
    return raw


def fetch_one(conn, table: str, pk: int, pk_col: str = "id") -> dict[str, Any] | None:
    rows = db.query(conn, f"SELECT * FROM {db.quote_ident(table)} WHERE {db.quote_ident(pk_col)}=%s;", (pk,))
    return rows[0] if rows else None
