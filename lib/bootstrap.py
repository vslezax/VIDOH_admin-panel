"""
Подготовка sys.path для скриптов, лежащих в подпапках проекта.

Когда скрипт запускается как `python events/view_events.py`, Python кладёт в
sys.path каталог `events/`, а не корень проекта, поэтому `import lib` не
находится. Функция ensure_project_root() поднимается вверх от текущего файла
до каталога, содержащего папку `lib/`, и добавляет его в sys.path.

Использование в начале любого скрипта из подпапки:

    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from lib import bootstrap; bootstrap.ensure_project_root()
    from lib import db, ui

Но проще: достаточно вызвать ensure_project_root() из корня, если он уже
импортируется — ниже приведён компактный блок, который вставляется в каждый
скрипт (см. шаблон в других файлах). Этот модуль — единая реализация.
"""
from __future__ import annotations

import sys
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path | None:
    """Ищет вверх по дереву каталог, где есть подпапка lib/."""
    cur = (start or Path(__file__).resolve()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "lib" / "__init__.py").is_file():
            return parent
    return None


def ensure_project_root() -> Path:
    """Добавляет корень проекта в sys.path (если ещё нет). Возвращает корень."""
    root = find_project_root()
    if root is None:
        # fallback: два уровня вверх от этого файла (lib/bootstrap.py -> проект)
        root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root
