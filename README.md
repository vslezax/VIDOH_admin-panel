# VDH-DB-connection

Консольные Python-скрипты для администрирования БД (PostgreSQL на Neon) и
S3-хранилища проекта VIDOH. Каждый скрипт работает с одной доменной областью и
запускается как отдельный процесс (своё соединение с БД).

## Требования

- Python 3.10+
- Виртуальное окружение `.venv` с зависимостями из `requirements.txt`
- Файл `.env` в корне проекта
- Доступ к БД Neon (переменная `DATABASE_URL`)

Установка зависимостей:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Настройка

Создайте файл `.env` в корне проекта и заполните:

- `DATABASE_URL` — строка подключения к PostgreSQL (Neon)
- `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`,
  `S3_BUCKET` — параметры S3-хранилища (Backblaze B2)

## Запуск

### Единая точка входа

```powershell
.\.venv\Scripts\python.exe run_admin.py
```

Открывается меню по доменам: DB, S3, EVENTS, ORGANIZERS, USERS, CATALOG,
TICKETS, MEDIA, SALES, REVIEWS, SERVICE. Выбор пункта запускает нужный скрипт.

### Отдельные скрипты

Любой скрипт можно запустить напрямую:

```powershell
.\.venv\Scripts\python.exe events\view_events.py
.\.venv\Scripts\python.exe catalog\view_cities.py
.\.venv\Scripts\python.exe sales\view_orders.py
```

## Структура

```
VDH-DB-connection/
├── lib/                общие модули (db, ui, s3, crud, bootstrap, delete_guard)
├── run_admin.py        единая точка входа (меню по доменам)
├── db/common/          view_db.py — сводка по БД
├── s3/common/          просмотр и синхронизация S3
├── events/             события, ссылки, расписания, документы, связи
├── organizers/         организаторы и контакты
├── users/              пользователи, сессии, избранное
├── catalog/            страны, города, площадки, категории
├── tickets/            билеты и промокоды
├── media/              медиа: просмотр, загрузка, правка, удаление
├── sales/              заказы, позиции, платежи, выданные билеты
├── reviews/            отзывы: просмотр, модерация, удаление
└── service/            сервисные скрипты (DBML->SQL, деплой, очистка, тест)
```

## Соглашения

- Формат файлов: `view_*`, `create_*`, `edit_*`, `delete_*` — отдельный скрипт
  на действие; линковочные таблицы (composite PK) — один `manage_*`.
- Все скрипты валидируют данные по схеме БД (CHECK/UNIQUE/FK/enum).
- Опасные операции (`delete_*`, `clear_database.py`) требуют ввода `yes` и
  заранее показывают зависимости (CASCADE / SET NULL / RESTRICT).
- Запросы параметризованы (psycopg2 `%s`); идентификаторы экранируются через
  `db.quote_ident`.

## Кодировка консоли (Windows)

Скрипты выводят кириллицу в UTF-8. Чтобы избежать «кракозябр» в консоли
Windows, `lib/__init__.py` при импорте переключает кодовую страницу консоли на
UTF-8 (65001) и настраивает потоки `stdin/stdout/stderr` на `utf-8`. Если
символы всё равно отображаются неверно, проверьте шрифт консоли (должен
поддерживать Юникод, напр. Consolas или Lucida Console) и кодовую страницу:

```powershell
chcp 65001
```