"""Общие модули для консольных скриптов админ-панели VIDOH."""
from __future__ import annotations

import sys


def _force_utf8_stdio() -> None:
    """Принудительно включает UTF-8 для stdin/stdout/stderr и консоли Windows.

    На Windows консоль часто работает в cp866/cp1251, а исходники и вывод —
    UTF-8. Без этого кириллица в меню и таблицах превращается в «кракозябры».
    Шаги:
      1) переключаем кодовую страницу консоли на UTF-8 (65001) через Win32;
      2) переводим текстовые потоки Python на encoding='utf-8'.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)  # CP_UTF8
            kernel32.SetConsoleCP(65001)
        except Exception:  # noqa: BLE001 — не критично, продолжаем
            pass

    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:  # noqa: BLE001 — не критично, работаем как есть
                pass


_force_utf8_stdio()