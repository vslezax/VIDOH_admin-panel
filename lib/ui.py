
"""
Пользовательский интерфейс для консольных скриптов админ-панели.

Всё, что касается ввода/вывода: цвета, заголовки, таблицы, пагинация,
подтверждения опасных операций, интерактивные меню.
"""
from __future__ import annotations

import sys
from typing import Any, Iterable, Sequence

# --- Цвета (авто-отключение, если вывод не в терминале или Windows без ANSI) ---
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def ok(text: str) -> str:
    return _c("92", text)


def fail(text: str) -> str:
    return _c("91", text)


def info(text: str) -> str:
    return _c("94", text)


def warn(text: str) -> str:
    return _c("93", text)


def dim(text: str) -> str:
    return _c("90", text)


def bold(text: str) -> str:
    return _c("1", text)


def header(text: str) -> None:
    line = "=" * 66
    print(f"\n{bold(line)}\n{bold(text)}\n{bold(line)}")


def section(text: str) -> None:
    print(f"\n{bold('--- ' + text + ' ' + '-' * max(0, 60 - len(text)))}")


# --- Ввод -------------------------------------------------------------------

def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{suffix}: ").strip()
    if not val and default is not None:
        return default
    return val


def ask_int(prompt: str, default: int | None = None) -> int | None:
    raw = ask(prompt, None if default is None else str(default))
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        print(fail("  Ожидалось целое число."))
        return ask_int(prompt, default)


def confirm(prompt: str) -> bool:
    """Требует явного 'yes' для опасных операций."""
    ans = input(f"{warn(prompt)} Введите 'yes' для подтверждения: ").strip().lower()
    return ans == "yes"


def pause() -> None:
    input(dim("\nНажмите Enter, чтобы продолжить..."))


# --- Таблицы ----------------------------------------------------------------

def _fmt_cell(value: Any, max_width: int) -> str:
    if value is None:
        s = ""
    elif isinstance(value, bool):
        s = "true" if value else "false"
    else:
        s = str(value)
    s = s.replace("\n", " ")
    if len(s) > max_width:
        s = s[: max_width - 1] + "…"
    return s


def print_table(
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    max_width: int = 40,
    empty_msg: str = "(нет данных)",
) -> None:
    rows = [list(r) for r in rows]
    if not rows:
        print(dim(f"  {empty_msg}"))
        return

    widths = [len(c) for c in columns]
    str_rows = []
    for r in rows:
        sr = [_fmt_cell(v, max_width) for v in r]
        str_rows.append(sr)
        for i, cell in enumerate(sr):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: Sequence[str]) -> str:
        return "  " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells))

    print(dim(fmt_row(columns)))
    print(dim("  " + "-+-".join("-" * w for w in widths)))
    for sr in str_rows:
        print(fmt_row(sr))


def menu(title: str, options: Sequence[tuple[str, str]]) -> str | None:
    """Показывает меню; options — список (key, label). Возвращает выбранный key."""
    header(title)
    for key, label in options:
        print(f"  [{key}] {label}")
    print(f"  [{dim('0')}] {dim('Выход')}")
    choice = input("\nВыберите пункт: ").strip()
    if choice == "0" or choice == "":
        return None
    return choice
