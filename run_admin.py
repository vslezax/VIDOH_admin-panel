"""
Единая точка входа админ-панели VDH-DB-connection.

Показывает меню по доменам и запускает выбранный скрипт как отдельный
процесс (subprocess) из корня проекта. Так сохраняется изоляция скриптов
(каждый работает со своим соединением) и корректный sys.path.

Запуск:  python run_admin.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# --- UTF-8 ??? ??????? Windows (????????? ??? ???????????) -------------------
if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:  # noqa: BLE001
        pass
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    _reconf = getattr(_stream, "reconfigure", None)
    if _reconf is not None:
        try:
            _reconf(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

ROOT = Path(__file__).resolve().parent

# домен -> список (пункт, описание, относительный путь скрипта)
DOMAINS: dict[str, list[tuple[str, str, str]]] = {
    "DB": [
        ("view_db.py", "Просмотр БД (сводка, структура)", "db/view_db.py"),
        ("create_database.py", "Создать схему из schema.dbml", "db/create_database.py"),
        ("reset_database.py", "ПОЛНЫЙ сброс БД", "db/reset_database.py"),
    ],
    "S3": [
        ("view_s3-storage.py", "Просмотр S3-хранилища", "s3/common/view_s3-storage.py"),
        ("sync_media-db-s3.py", "Синхронизация медиа БД<->S3", "s3/common/sync_media-db-s3.py"),
    ],
    "EVENTS": [
        ("view_events.py", "Список/карточка событий", "events/view_events.py"),
        ("create_event.py", "Создать событие", "events/create_event.py"),
        ("edit_event.py", "Редактировать событие", "events/edit_event.py"),
        ("delete_event.py", "Удалить событие", "events/delete_event.py"),
        ("manage_event-categories.py", "Категории события", "events/manage_event-categories.py"),
        ("manage_event-organizers.py", "Организаторы события", "events/manage_event-organizers.py"),
        ("manage_event-media.py", "Медиа события", "events/manage_event-media.py"),
        ("view_event-links.py", "Ссылки события (просмотр)", "events/view_event-links.py"),
        ("create_event-link.py", "Создать ссылку", "events/create_event-link.py"),
        ("edit_event-link.py", "Редактировать ссылку", "events/edit_event-link.py"),
        ("delete_event-link.py", "Удалить ссылку", "events/delete_event-link.py"),
        ("view_event-schedules.py", "Расписания (просмотр)", "events/view_event-schedules.py"),
        ("create_event-schedule.py", "Создать расписание", "events/create_event-schedule.py"),
        ("edit_event-schedule.py", "Редактировать расписание", "events/edit_event-schedule.py"),
        ("delete_event-schedule.py", "Удалить расписание", "events/delete_event-schedule.py"),
        ("view_event-documents.py", "Документы (просмотр)", "events/view_event-documents.py"),
        ("create_event-document.py", "Создать документ", "events/create_event-document.py"),
        ("edit_event-document.py", "Редактировать документ", "events/edit_event-document.py"),
        ("delete_event-document.py", "Удалить документ", "events/delete_event-document.py"),
    ],
    "ORGANIZERS": [
        ("view_organizers.py", "Список/карточка организаторов", "organizers/view_organizers.py"),
        ("create_organizer.py", "Создать организатора", "organizers/create_organizer.py"),
        ("edit_organizer.py", "Редактировать организатора", "organizers/edit_organizer.py"),
        ("delete_organizer.py", "Удалить организатора", "organizers/delete_organizer.py"),
        ("manage_organizer-contacts.py", "Контакты организатора", "organizers/manage_organizer-contacts.py"),
    ],
    "USERS": [
        ("view_users.py", "Список/карточка пользователей", "users/view_users.py"),
        ("create_user.py", "Создать пользователя", "users/create_user.py"),
        ("edit_user.py", "Редактировать пользователя", "users/edit_user.py"),
        ("delete_user.py", "Удалить пользователя", "users/delete_user.py"),
        ("manage_user-sessions.py", "Сессии пользователя", "users/manage_user-sessions.py"),
        ("manage_user-favorites.py", "Избранное пользователя", "users/manage_user-favorites.py"),
    ],
    "CATALOG": [
        ("view_categories.py", "Категории (просмотр)", "catalog/view_categories.py"),
        ("create_category.py", "Создать категорию", "catalog/create_category.py"),
        ("edit_category.py", "Редактировать категорию", "catalog/edit_category.py"),
        ("delete_category.py", "Удалить категорию", "catalog/delete_category.py"),
        ("view_countries.py", "Страны (просмотр)", "catalog/view_countries.py"),
        ("create_country.py", "Создать страну", "catalog/create_country.py"),
        ("edit_country.py", "Редактировать страну", "catalog/edit_country.py"),
        ("delete_country.py", "Удалить страну", "catalog/delete_country.py"),
        ("view_cities.py", "Города (просмотр)", "catalog/view_cities.py"),
        ("create_city.py", "Создать город", "catalog/create_city.py"),
        ("edit_city.py", "Редактировать город", "catalog/edit_city.py"),
        ("delete_city.py", "Удалить город", "catalog/delete_city.py"),
        ("view_venues.py", "Площадки (просмотр)", "catalog/view_venues.py"),
        ("create_venue.py", "Создать площадку", "catalog/create_venue.py"),
        ("edit_venue.py", "Редактировать площадку", "catalog/edit_venue.py"),
        ("delete_venue.py", "Удалить площадку", "catalog/delete_venue.py"),
        ("view_metro-stations.py", "Станции метро (просмотр)", "catalog/view_metro-stations.py"),
        ("create_metro-station.py", "Создать станцию метро", "catalog/create_metro-station.py"),
        ("edit_metro-station.py", "Редактировать станцию метро", "catalog/edit_metro-station.py"),
        ("delete_metro-station.py", "Удалить станцию метро", "catalog/delete_metro-station.py"),
    ],
    "TICKETS": [
        ("view_tickets.py", "Билеты (просмотр)", "tickets/view_tickets.py"),
        ("create_ticket.py", "Создать билет", "tickets/create_ticket.py"),
        ("edit_ticket.py", "Редактировать билет", "tickets/edit_ticket.py"),
        ("delete_ticket.py", "Удалить билет", "tickets/delete_ticket.py"),
        ("view_promo-codes.py", "Промокоды (просмотр)", "tickets/view_promo-codes.py"),
        ("create_promo-code.py", "Создать промокод", "tickets/create_promo-code.py"),
        ("edit_promo-code.py", "Редактировать промокод", "tickets/edit_promo-code.py"),
        ("delete_promo-code.py", "Удалить промокод", "tickets/delete_promo-code.py"),
    ],
    "MEDIA": [
        ("view_media.py", "Медиа (просмотр)", "media/view_media.py"),
        ("upload_media.py", "Загрузить медиа", "media/upload_media.py"),
        ("edit_media.py", "Редактировать медиа", "media/edit_media.py"),
        ("delete_media.py", "Удалить медиа", "media/delete_media.py"),
    ],
    "SALES": [
        ("view_orders.py", "Заказы (просмотр)", "sales/view_orders.py"),
        ("create_order.py", "Создать заказ", "sales/create_order.py"),
        ("edit_order.py", "Редактировать заказ", "sales/edit_order.py"),
        ("delete_order.py", "Удалить заказ", "sales/delete_order.py"),
        ("view_order-items.py", "Позиции заказа (просмотр)", "sales/view_order-items.py"),
        ("create_order-item.py", "Создать позицию", "sales/create_order-item.py"),
        ("edit_order-item.py", "Редактировать позицию", "sales/edit_order-item.py"),
        ("delete_order-item.py", "Удалить позицию", "sales/delete_order-item.py"),
        ("view_payments.py", "Платежи (просмотр)", "sales/view_payments.py"),
        ("edit_payment-status.py", "Изменить статус платежа", "sales/edit_payment-status.py"),
        ("view_issued-tickets.py", "Выданные билеты (просмотр)", "sales/view_issued-tickets.py"),
        ("create_issued-ticket.py", "Создать выданный билет", "sales/create_issued-ticket.py"),
        ("edit_issued-ticket-status.py", "Статус выданного билета", "sales/edit_issued-ticket-status.py"),
        ("delete_issued-ticket.py", "Удалить выданный билет", "sales/delete_issued-ticket.py"),
    ],
    "REVIEWS": [
        ("view_reviews.py", "Отзывы (просмотр)", "reviews/view_reviews.py"),
        ("moderate_reviews.py", "Модерация отзыва", "reviews/moderate_reviews.py"),
        ("delete_review.py", "Удалить отзыв", "reviews/delete_review.py"),
    ],
    "SERVICE": [
        ("convert_dbml-to-sql.py", "DBML -> SQL", "service/convert_dbml-to-sql.py"),
        ("deploy_schema.py", "Развернуть схему в БД", "service/deploy_schema.py"),
        ("clear_database.py", "Очистить БД (DROP schema public)", "service/clear_database.py"),
        ("test_db-connection.py", "Тест подключения/схемы", "service/test_db-connection.py"),
        ("backup_snapshot.py", "Снапшот БД + S3", "service/backup_snapshot.py"),
        ("restore_snapshot.py", "Восстановление из снапшота", "service/restore_snapshot.py"),
    ],
}


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\nНажмите Enter, чтобы продолжить...")


def choose(domain: str) -> str | None:
    items = DOMAINS[domain]
    while True:
        clear()
        print("=" * 64)
        print(f" VDH ADMIN — {domain}")
        print("=" * 64)
        for i, (name, desc, _) in enumerate(items, 1):
            print(f"  [{i:>2}] {name:<32} {desc}")
        print("  [ 0] Назад")
        print("=" * 64)
        raw = input("Выбор: ").strip()
        if raw == "0" or raw == "":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1][2]
        print("Нет такого пункта.")


def run_script(rel_path: str) -> None:
    script = ROOT / rel_path
    if not script.exists():
        print(f"Скрипт не найден: {script}")
        pause()
        return
    clear()
    print(f"Запуск: {rel_path}\n")
    try:
        subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=False)
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")


def main() -> int:
    domains = list(DOMAINS.keys())
    while True:
        clear()
        print("=" * 64)
        print(" VDH-DB-connection — админ-панель")
        print("=" * 64)
        for i, d in enumerate(domains, 1):
            print(f"  [{i:>2}] {d}")
        print("  [ 0] Выход")
        print("=" * 64)
        raw = input("Выберите домен: ").strip()
        if raw == "0" or raw == "":
            break
        if raw.isdigit() and 1 <= int(raw) <= len(domains):
            domain = domains[int(raw) - 1]
            # подменю домена до возврата
            while True:
                script = choose(domain)
                if script is None:
                    break
                run_script(script)
                pause()
        else:
            print("Нет такого домена.")
    print("Пока.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
