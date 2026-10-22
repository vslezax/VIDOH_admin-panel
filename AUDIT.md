# VDH-DB-connection — АУДИТ: баги, недоделки, ошибки

Документ составлен по результатам статического просмотра **всех** скриптов
проекта (92 `.py`-файла вне `.venv`) и сверки с реальной схемой БД
(`schema.sql.txt` / `VIDOH.dbml`) и с API общих модулей `lib/`.

> Этот файл рассчитан на то, чтобы быть **самодостаточным**: сначала идёт
> описание проекта, структуры и модели данных (раздел «Контекст проекта»),
> затем — непосредственно результаты аудита. Если вы читаете впервые —
> начните с контекста, чтобы понимать назначение файлов, упоминаемых ниже.

## Содержание

- **Контекст проекта**: К.1 назначение · К.2 стек · К.3 конфигурация ·
  К.4 структура · К.5 соглашения · К.6 общие модули `lib/` · К.7 модель данных ·
  К.8 запуск
- **Результаты аудита**: статус проверок · 1 КРИТ · 2 БАГ · 3 НЕДОДЕЛ ·
  4 МЕЛОЧЬ · 5 БЕЗОП · 6 документация · 7 порядок исправлений ·
  Приложение A (перечень файлов)

---

# КОНТЕКСТ ПРОЕКТА

## К.1. Что это за проект

**VDH-DB-connection** — набор **консольных (CLI) Python-скриптов для
администрирования** проекта «VIDOH» (платформа мероприятий/билетов). Скрипты
позволяют вручную просматривать и изменять данные в двух хранилищах:

- **PostgreSQL (облачный Neon)** — основная реляционная БД (пользователи,
  организаторы, события, билеты, заказы, платежи и т.д.);
- **S3-совместимое хранилище (Backblaze B2)** — файловое хранилище медиа
  (изображения, видео, документы).

Каждый скрипт — это **отдельный процесс со своим соединением к БД** и
интерактивным меню/диалогом. Скрипты не являются сервисом/API и не
предназначены для работы в вебе — это инструменты оператора/администратора,
запускаемые вручную из терминала.

Назначение и «философия»:
- **Обход ограничений облачных админок**: прямой доступ к Neon/Backblaze без
  веб-панели, для точечных операций и отладки.
- **Безопасность данных**: опасные операции (`delete_*`, очистка БД) требуют
  явного подтверждения `yes` и предварительно показывают зависимости.
- **Соблюдение схемы**: скрипты валидируют данные по ограничениям БД
  (CHECK/UNIQUE/FK/enum) до отправки запроса.

## К.2. Технологический стек

- **Python 3.10+** (используется `from __future__ import annotations`,
  type-hints вида `X | None`).
- **psycopg2-binary** — доступ к PostgreSQL/Neon (`RealDictCursor`, строки как
  `dict`).
- **python-dotenv** — чтение `.env` в корне проекта.
- **boto3** — S3-клиент для Backblaze B2.
- **lark-dbml / sqlglot** — только для `service/convert_dbml-to-sql.py`
  (конвертация `VIDOH.dbml` → SQL).
- **Pillow** — только для `media/upload_media.py` (размеры изображений).
- Требования зафиксированы в `requirements.txt`; окружение — в `.venv`.

## К.3. Конфигурация (`.env` в корне)

Секреты и параметры подключения хранятся в `.env` (в репозиторий не
коммитится). Ключевые переменные:

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | строка подключения к PostgreSQL (Neon) |
| `S3_ENDPOINT_URL` | эндпоинт Backblaze, напр. `https://s3.eu-central-003.backblazeb2.com` |
| `S3_REGION` | регион из эндпоинта, напр. `eu-central-003` |
| `S3_ACCESS_KEY_ID` | Application Key ID |
| `S3_SECRET_ACCESS_KEY` | Application Key |
| `S3_BUCKET` | бакет по умолчанию |

`.env`, `.venv`, `__pycache__`, `*.pyc` исключены через `.gitignore`.
Секреты в код не зашиваются (единственный исторически захардкоженный
`DATABASE_URL` был в удалённом `Create-DB-Neon.py`, см. «Безопасность»).

## К.4. Структура проекта (дерево)

```
VDH-DB-connection/
├── lib/                    общие модули (переиспользуются всеми скриптами)
│   ├── __init__.py         принудительный UTF-8 для консоли Windows
│   ├── db.py               подключение к PostgreSQL, query/execute, метаданные
│   ├── ui.py               консольный UI: цвета, таблицы, меню, confirm
│   ├── crud.py             хелперы ввода полей + INSERT/UPDATE + pick_id
│   ├── s3.py               клиент S3 (B2): конфиг, list/upload, URL, ошибки
│   ├── bootstrap.py        поиск корня проекта для sys.path
│   └── delete_guard.py     проверка зависимостей (FK) перед удалением
├── run_admin.py            ЕДИНАЯ точка входа: меню по доменам -> подпроцесс
├── db/common/view_db.py    сводка/структура/поиск по БД
├── s3/common/              просмотр S3 и синхронизация медиа БД<->S3
│   ├── view_s3-storage.py
│   └── sync_media-db-s3.py
├── events/                 события, ссылки, расписания, документы, связи (19)
├── organizers/             организаторы и контакты (5)
├── users/                  пользователи, сессии, избранное (6)
├── catalog/                страны, города, площадки, категории (16)
├── tickets/                билеты и промокоды (8)
├── media/                  медиа: просмотр/загрузка/правка/удаление (4)
├── sales/                  заказы, позиции, платежи, выданные билеты (14)
├── reviews/                отзывы: просмотр/модерация/удаление (3)
├── service/                сервисные/опасные скрипты (конвертация, деплой,
│                           очистка, тест, снапшот, восстановление)
├── VIDOH.dbml              исходная схема (DBML)
├── schema.sql.txt          SQL-схема (DDL + FK) — см. недоделку 3.1
├── requirements.txt        зависимости
├── README.md               краткое руководство
└── SUMMARY.txt             история реорганизации проекта (историческ.)
```

## К.5. Соглашения об именовании и архитектуре

- **Один скрипт = одно действие**: `view_*`, `create_*`, `edit_*`,
  `delete_*`. Это позволяет запускать/отлаживать точечно без меню.
- **Линковочные таблицы** с составным PK (`event_media`, `event_categories`,
  `event_organizers`, `organizer_contacts`, `user_sessions`,
  `user_favorites`) управляются **одним** скриптом `manage_*` (add/remove/list).
- **Стандартный заголовок файла подпапки** (навигация по `sys.path`):
  ```python
  from __future__ import annotations
  import os, sys
  _proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
  if _proj_root not in sys.path:
      sys.path.insert(0, _proj_root)
  from lib import crud, db, ui
  ```
  Для `db/common` и `s3/common` глубина `"..\.."`.
- **Потоки выполнения**: `main() -> int`; подключение в `try`,
  `conn.close()` в `finally`; ошибки БД перехватываются и печатаются
  через `ui.fail`.
- **Параметризованные запросы** (`psycopg2 %s`); идентификаторы экранируются
  через `db.quote_ident`. `autocommit=True` (см. `lib/db.connect`).
- **UTF-8 в консоли Windows**: `lib/__init__.py` при импорте ставит кодовую
  страницу 65001 и перенастраивает `stdin/stdout/stderr` на `utf-8`, чтобы
  кириллица не превращалась в «кракозябры».

## К.6. Ключевые общие модули `lib/` (API, на который завязаны скрипты)

**`lib/db.py`**
- `connect()` → psycopg2-соединение (`autocommit=True`), URL из `DATABASE_URL`.
- `query(conn, sql, params)` → `list[dict]` (со `scalarize` дат/Decimal/UUID).
- `execute(conn, sql, params)` → `rowcount`.
- `quote_ident(name)` — экранирование идентификатора.
- метаданные: `list_tables`, `table_columns`, `table_count`,
  `table_size_pretty`.

**`lib/ui.py`**
- цвета: `ok/fail/info/warn/dim/bold`; блоки: `header/section`.
- ввод: `ask`, `ask_int`, `confirm` (требует `yes`), `pause`.
- `print_table(columns, rows, max_width)` — табличный вывод.
- `menu(title, options)` → выбранный ключ или `None` (0/Enter).

**`lib/crud.py`** — центральный слой для CRUD-скриптов:
- ввод полей: `ask_text`, `ask_int`, `ask_decimal`, `ask_bool`, `ask_enum`,
  `ask_datetime`, `ask_fk(...)`; константа `NULL_TOKENS`.
- вывод diff: `show_diff(mapping, before=None)`.
- запись: `run_insert(conn, table, data, returning="id")`,
  `run_update(conn, table, pk, data)`.
- чтение/выбор: `list_rows`, `print_rows`, `pick_id`, `fetch_one`.

**`lib/s3.py`** — обёртка boto3 для Backblaze B2: `load_config`,
`is_configured`, `make_client`, `list_objects`, `build_public_url`,
`media_type_from_mime`, `friendly_error`, `human_size`, `accessible_buckets`,
`verify`.

**`lib/delete_guard.py`** — перед удалением:
`collect_dependencies(conn, table, pk)` находит все FK на запись и считает
зависимые строки по правилу `ON DELETE` (CASCADE/SET NULL/SET DEFAULT/
RESTRICT/NO ACTION); `report_dependencies(deps)` печатает отчёт и возвращает
`False`, если есть блокирующие (RESTRICT/NO ACTION) зависимости.

## К.7. Модель данных (обзор схемы)

Схема описана в `VIDOH.dbml` и развёрнута в `schema.sql.txt`. ENUM-типы:
`user_status`, `organizer_status`, `organizer_legal_form`, `event_status`,
`media_type`, `media_role`, `link_type`, `document_type`, `review_status`,
`order_status`, `ticket_status`, `promo_discount_type`, `schedule_kind`,
`contact_type`, `payment_status`.

Таблицы по доменам (PK — `id BIGINT GENERATED ... AS IDENTITY`, у большинства
пользовательских сущностей есть `uuid`, `created_at`, `updated_at`,
`deleted_at` — мягкое удаление):

- **users**: `users` (email CITEXT / phone, CHECK email ИЛИ phone),
  `user_sessions` (FK→users CASCADE, `ip INET`), `user_favorites`
  (PK user_id+event_id, оба CASCADE).
- **organizers**: `organizers` (slug UNIQUE, legal_form/status enum,
  avatar/cover media SET NULL), `organizer_contacts` (FK→organizers CASCADE).
- **catalog**: `countries` (iso UNIQUE), `cities` (FK→countries NO ACTION,
  UNIQUE(country_id, slug), CHECK lat/lng), `venues` (FK→cities NO ACTION,
  UNIQUE(city_id, slug), CHECK lat/lng/capacity), `categories`
  (slug UNIQUE, icon media SET NULL).
- **media**: `media` (storage_key UNIQUE, type enum, CHECK width/height/size,
  uploaded_by→users SET NULL).
- **events** (ядро): `events` (uuid/slug UNIQUE, FK→venues SET NULL,
  CHECK venue ИЛИ online_url, age_rating enum-набор 0/6/12/16/18, capacity≥0);
  связи: `event_media` (CASCADE), `event_organizers` (CASCADE,
  partial UNIQUE primary), `event_categories` (CASCADE, partial UNIQUE primary);
  дочерние: `event_links` (CHECK url ^https?://), `event_schedules`
  (CHECK по kind: once→start_at, recurring→recurrence; utc_offset `±HH:MM`),
  `event_documents` (CHECK content ИЛИ url).
- **tickets**: `tickets` (FK→events CASCADE, CHECK sold≤count, price≥0),
  `promo_codes` (code UNIQUE, FK→events SET NULL, CHECK percent≤100,
  max_uses, valid_to>valid_from).
- **sales**: `orders` (uuid UNIQUE, FK→users/events NO ACTION,
  promo_code SET NULL, total_amount≥0), `order_items` (FK→orders CASCADE,
  FK→tickets NO ACTION, quantity>0), `issued_tickets` (uuid/code UNIQUE,
  FK→order_item/user/event NO ACTION, CHECK status='used'⇔checked_in_at NOT NULL),
  `payments` (FK→orders CASCADE, amount>0, UNIQUE(provider, provider_txn/idempotency_key)).
- **reviews**: `event_reviews` (FK→events/users CASCADE, CHECK rating 1..5,
  UNIQUE(event_id, user_id)).

Правила `ON DELETE`, важные для `delete_guard`: удаление `events` каскадно
удаляет медиа/связи/расписания/документы/билеты/избранное/отзывы, но
**блокируется** при наличии `orders`/`issued_tickets` (NO ACTION) и
обнуляет `promo_codes.event_id` (SET NULL).

## К.8. Как запускать

Единая точка входа (меню по доменам: DB, S3, EVENTS, ORGANIZERS, USERS,
CATALOG, TICKETS, MEDIA, SALES, REVIEWS, SERVICE):

```powershell
.\.venv\Scripts\python.exe run_admin.py
```

Любой скрипт напрямую:

```powershell
.\.venv\Scripts\python.exe events\view_events.py
.\.venv\Scripts\python.exe catalog\view_cities.py
.\.venv\Scripts\python.exe sales\view_orders.py
```

Сервисные скрипты поддерживают аргументы CLI, например:
`service/backup_snapshot.py --label before-migration --zip`,
`service/restore_snapshot.py --list`,
`service/restore_snapshot.py --snapshot <name> --prefer-sql --yes`.

Установка окружения:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

---

# РЕЗУЛЬТАТЫ АУДИТА

## Статус проверок

- [x] Компиляция всех файлов: `.\.venv\Scripts\python.exe -m py_compile` по 92
      файлам — **код возврата 0, синтаксических ошибок нет**.
- [ ] Сквозной runtime-прогон (смоук-тест против живой БД) — **НЕ выполнен**:
      в текущем окружении нет рабочего `.env`/доступа к Neon, скрипты
      интерактивны и ждут ввода (запуск в неинтерактивной среде зависает на
      `input()`). Все выводы ниже — из чтения кода и сверки со схемой.

Классификация: **[КРИТ]** — ломает работу/данные; **[БАГ]** — неверное
поведение в реальном сценарии; **[НЕДОДЕЛ]** — неполная функциональность;
**[МЕЛОЧЬ]** — косметика/устойчивость; **[БЕЗОП]** — безопасность.

---

## 1. [КРИТ] Ошибки, способные приводить к падению/порче данных

### 1.1. `service/backup_snapshot.py` — падение на Windows из-за `os.uname()`
Строка формирования `host` в манифесте:
```python
"host": os.getenv("COMPUTERNAME") or os.uname().nodename if hasattr(os, "uname") else os.getenv("COMPUTERNAME", ""),
```
- На Windows `os.uname` отсутствует (проверено: `hasattr(os,'uname') == False`),
  поэтому ветка `or os.uname().nodename` **не** вычисляется только благодаря
  тому, что левая часть обычно истинна. Но приоритет операторов здесь опасен:
  выражение разбирается как
  `(os.getenv("COMPUTERNAME") or os.uname().nodename) if hasattr(...) else os.getenv(...)`.
  На Windows `hasattr(...)` == False → берётся правая ветка (безопасно), **но**
  логика запутана и хрупка. На Linux/macOS, наоборот, при наличии
  `COMPUTERNAME` поведение отличается от задуманного.
- **Риск уровня [БАГ]/[МЕЛОЧЬ]**, но легко превращается в `AttributeError`,
  если код скопируют/перепишут. Заменить на:
  ```python
  import platform
  "host": platform.node(),
  ```

### 1.2. `sales/create_order-item.py` — `quantity` может уйти как `NULL`
```python
ch, qty = crud.ask_int("quantity", required=True, min_value=1)
data["quantity"] = qty
```
`crud.ask_int` при вводе одного из `NULL_TOKENS` (`null`, `-`, `none`, `пусто`)
возвращает `(True, None)` **даже при `required=True`** (проверка `required`
срабатывает только на **пустом** вводе, а не на null-токене). В итоге
`quantity=None` → `INSERT ... VALUES (..., NULL, ...)` → нарушение `NOT NULL`
(`order_items.quantity`). Пользователь увидит техническую ошибку БД вместо
подсказки.
- Аналогичный паттерн есть в других `create_*`, где `required=True`
  результат присваивается без проверки на `None` (см. п. 2.1).

### 1.3. `service/restore_snapshot.py` — восстановление из `dump.json` игнорирует транзакционность
```python
with conn.cursor() as cur:
    for r in rows:
        cur.execute(sql, [r.get(c) for c in cols])
```
`conn.autocommit = True` (см. `lib/db.connect`). Если вставка упадёт на строке
N, уже вставленные строки **останутся** в БД (частичное восстановление), а
`TRUNCATE ... CASCADE` перед этим уже стёр данные. Итог — потенциально
неконсистентная БД. Нужно оборачивать весь цикл в одну транзакцию
(`with conn: ...` / временно `autocommit=False`) либо выполнять через
`psycopg2.extras.execute_values` в явной транзакции.

---

## 2. [БАГ] Некорректное поведение в реальных сценариях

### 2.1. `crud.ask_*` + проверка `required`
`lib/crud.py`: `ask_text/ask_int/ask_decimal` при вводе null-токена возвращают
`None`, невзирая на `required`. Скрипты, которые делают
`_, x = crud.ask_*(..., required=True)` и затем сразу `data[...] = x`, не
проверяют `x is not None`:
- `catalog/create_city.py` (`name`, `slug` — есть частичная проверка `if not name`);
- `catalog/create_venue.py` (`name`, `slug`, `address` — проверяются);
- `tickets/create_ticket.py` (`price` → присваивается `0` если None — ок);
- `sales/create_order-item.py` (`quantity`, `unit_price`, `total_price`);
- `events/create_event.py` (`slug`, `title` — проверяются).

Наиболее проблемный — `create_order-item.py` (см. 1.2). Рекомендация: в
`crud.ask_*` при `required=True` не принимать null-токены (переспрашивать),
либо добавить в скрипты проверку возвращённого значения.

### 2.2. `lib/crud.ask_fk` — проверка существования только по колонке `id`
```python
exists = db.query(conn, f"SELECT {cols_sql} FROM {ref_table} WHERE id=%s;", (val,))
```
Функция жёстко предполагает наличие колонки `id` во всех справочных таблицах.
Сейчас во всех используемых таблицах `id` есть, но:
- для линковочных/составных ключей и на будущее это ограничение неявно;
- подсказка `SELECT id, {cols_sql} ... ORDER BY id LIMIT 10` тоже требует `id`.
Технически работает, но является скрытым допущением — задокументировать.

### 2.3. `lib/ui.menu` возвращает произвольную строку без валидации
```python
choice = input(...).strip()
if choice == "0" or choice == "": return None
return choice
```
Валидацию делает вызывающий код. В большинстве `manage_*`/`view_db` есть
`else: print("Нет такого пункта.")`, но `menu()` не ограничивает значения —
при неверном вводе просто печатается предупреждение и снова цикл. Это
не ошибка, но интерфейс не защищён от лишних пробелов/регистра. [МЕЛОЧЬ].

### 2.4. `events/edit_event.py` — «пустой» вызов `print_table` как no-op
```python
ui.print_table(["поле", "было → станет"], [])  # noop, для единообразия заголовка
```
При пустом списке строк `print_table` печатает `(нет данных)` — то есть
лишнюю строку-заглушку после нормального diff. Убрать.

### 2.5. `sales/edit_order.py` — не обновляется `total_amount` каскадно/не проверяется против позиций
Редактор заказа меняет `total_amount` вручную, никак не сверяя с суммой
`order_items`. Логической проверки нет (это не DB-инвариант, но бизнес-риск
несогласованных сумм). [НЕДОДЕЛ].

### 2.6. `tickets/edit_promo-code.py` / `create_promo-code.py` — сравнение дат как строк
```python
if str(data["valid_to"]) <= str(data["valid_from"]):
```
`ask_datetime` возвращает строку `ISO` формата `YYYY-MM-DD HH:MM[:SS]`.
Строковое сравнение **работает корректно только** если обе даты в одном
формате. Если одна введена с секундами (`...:SS`), а другая без — сравнение
может дать ложный результат (например `"2025-01-01 10:00" > "2025-01-01 10:00:30"`
строково → `False`, хотя по времени это так). Рекомендация: парсить в
`datetime` перед сравнением. [БАГ].

### 2.7. `users/manage_user-sessions.py` — `ip` без валидации INET
```python
ip = ui.ask("ip (Enter — пусто)").strip() or None
```
Колонка `user_sessions.ip` имеет тип `INET`. Любая строка, не являющаяся
валидным IP, вызовет ошибку вставки на стороне БД (перехватывается общим
`try`, но пользователю выдаётся техническое сообщение). Добавить валидацию
через `ipaddress.ip_address`. [БАГ].

### 2.8. `currency` (CHAR(3)) не валидируется по длине
`orders`, `tickets`, `events`, `payments` — `currency CHAR(3)`. Скрипты
принимают `ui.ask("currency", default="RUB").strip().upper()` без проверки
длины. Строка длиной >3 вызовет ошибку `value too long for type character(3)`;
строки длиной <3 дополняются пробелами. Валидировать `len == 3` и, желательно,
по списку ISO-4217. [БАГ].

---

## 3. [НЕДОДЕЛ] Незавершённая / отсутствующая функциональность

### 3.1. `schema.sql` отсутствует в репозитории
В `SUMMARY.txt` и в комментариях `service/*` упоминается `ROOT/schema.sql`, но
в корне лежит только **`schema.sql.txt`** (см. примечание в самом SUMMARY).
`service/deploy_schema.py` и `service/restore` рассчитывают на `schema.sql`.
Нужно переименовать/добавить `schema.sql` либо заставить скрипты читать
`schema.sql.txt`. Сейчас развёртывание схемы «из коробки» не работает.

### 3.2. Генератор расписаний: `once` c `start_at` реализован, но `recurrence` не валидируется по формату
`events/create_event-schedule.py` принимает `recurrence` как произвольную
строку (`FREQ=WEEKLY` или текст). В схеме — `VARCHAR(255)` без CHECK, так что
это допустимо, но функционально «расписание» без разбора recurrence — заглушка.
[НЕДОДЕЛ].

### 3.3. Модерация отзывов не позволяет менять `rating`/`text`
`reviews/moderate_reviews.py` меняет только `status`. Комментарий в шапке
объясняет, что рейтинг не трогаем, но для полноценного CRUD модерации
обычно нужна правка текста/рейтинга (или отдельный `edit_review`). [НЕДОДЕЛ].

### 3.4. Нет скриптов управления `payments` кроме смены статуса
`sales/`: есть `view_payments.py` и `edit_payment-status.py`, но нет
`create_payment.py` / `delete_payment.py`. Для таблицы `payments` (с
`raw_payload`, `idempotency_key`) полноценного CRUD нет — в отличие от
остальных доменов. [НЕДОДЕЛ].

### 3.5. `media/upload_media.py` — список разрешённых расширений не применяется
`ALLOWED_DEFAULT` определён, но используется только для **предупреждения**,
не для блокировки. Проверка MIME ↔ расширение отсутствует; тип (`image/video/doc`)
определяется из MIME, но пользователь может переопределить вручную. Осознанно
«мягко», но помечено как недоделка контроля. [НЕДОДЕЛ]/[БЕЗОП].

### 3.6. `media/upload_media.py` — откат S3 при ошибке БД не откатывает частично
Откат (удаление объекта из S3) есть, но если `delete_object` тоже упадёт —
останется «сирота» в S3. Логируется, но не ретраится. [МЕЛОЧЬ].

### 3.7. `run_admin.py` — SERVICE-меню содержит `backup_snapshot.py`/`restore_snapshot.py`, которых не было в SUMMARY
Меню обновлено (это плюс), но в `SUMMARY.txt` раздел 3.5 перечисляет только 4
сервисных скрипта. Документация рассинхронизирована с кодом. [НЕДОДЕЛ-док].

### 3.8. Нет unit-/интеграционных тестов
`service/test_db-connection.py` — это лишь smoke-проверка подключения, не
тесты. Нет ни одного автотеста CRUD/валидации. Смоук-тест из SUMMARY
(запуск `view_*`) в CI не автоматизирован. [НЕДОДЕЛ].

---

## 4. [МЕЛОЧЬ] Косметика, устойчивость, дублирование

### 4.1. Двойной `import sys` в нескольких файлах
`db/common/view_db.py`, `media/upload_media.py`, `media/edit_media.py`,
`media/delete_media.py`:
```python
import os, sys            # первый sys
_proj_root = ...
import sys                # повторно
```
Безвредно, но неаккуратно. Убрать дубли (и `import sys` после
`from __future__` в перемещённых файлах — см. 4.2).

### 4.2. `from __future__ import annotations` + `import sys` между ним и кодом
В `media/*.py` и `db/common/view_db.py` порядок импортов перемешан
(`__future__`, затем `import os, sys`, затем блок `sys.path`, затем снова
`import sys`). Работает, но нарушает стиль. [МЕЛОЧЬ].

### 4.3. `db.quote_ident` не используется для `order` в `crud.list_rows`
```python
def list_rows(..., order="id DESC", ...):
    ...
    sql += f" ORDER BY {order} LIMIT %s;"
```
`order` подставляется как есть (не параметризуется). Сейчас вызывающие
передают фиксированные строки, но это потенциальная точка SQL-инъекции,
если аргумент станет пользовательским. Ограничить/задокументировать. [БЕЗОП].

### 4.4. `crud.ask_enum` — регистрозависимый набор при выводе, но `lower()` при вводе
Пользователю показываются значения как есть (`main|gallery|...`), ввод
приводится к `lower()`. Если в enum есть значения с верхним регистром — сломается.
Сейчас все enum в схеме в нижнем регистре — ок, но хрупко. [МЕЛОЧЬ].

### 4.5. `lib/ui.ui`-цвета: `_USE_COLOR = sys.stdout.isatty()` фиксируется при импорте
Если импорт произошёл до перенастройки потока (см. `lib/__init__._force_utf8_stdio`),
значение `isatty()` может быть некорректным после `reconfigure`. Не критично. [МЕЛОЧЬ].

### 4.6. Магические строки статусов/enum дублируются в каждом файле
`STATUSES`, `ROLE`, `DOC_TYPES`, `LINK_TYPES`, `CONTACT_TYPES` и т.п.
скопированы по файлам. При изменении enum в схеме надо править N файлов.
Вынести в общий `lib/enums.py`. [НЕДОДЕЛ]/[МЕЛОЧЬ].

### 4.7. `crud.show_diff` + `now()` в апдейтах
В `edit_*` маппинг `updates` содержит `"updated_at": "now()"`, а `show_diff`
печатает `... → now()`. Это нормально, но в `events/edit_event.py` перед
`show_diff` кладётся `now()` **после** вызова `crud.show_diff(updates, before=e)`?
Проверено: в `edit_event.py` `updated_at` добавляется **после** `show_diff` —
значит в diff строки `updated_at` нет, что ок. Но в `edit_venue.py`,
`edit_organizer.py`, `edit_ticket.py` — `updated_at` добавляется **до**
`show_diff` (в `edit_venue`, `edit_organizer`) → в таблицу изменений попадёт
служебная строка `updated_at → now()`. Непоследовательно; выровнять. [МЕЛОЧЬ].

### 4.8. `db.scalarize` для `Decimal` теряет формат валюты/точность
`f"{value:g}"` для `Decimal('1234.50')` даёт `1234.5`, для больших чисел может
перейти в экспоненциальную запись. Для денежных полей (`price`, `total_amount`,
`amount`) желательно фиксированное `2` знака. [МЕЛОЧЬ].

### 4.9. Дублирование в `media/upload_media.py` S3-ключей
`_make_storage_key` и `_make_custom_storage_key` почти идентичны — можно
объединить. [МЕЛОЧЬ].

### 4.10. `view_s3-storage.py`, `sync_media-db-s3.py` не проверены в этом аудите на 100%
Отдельный просмотр: они перенесены из корня, используют `..\..` и `lib.s3` —
проверить их логику синхронизации (деструктивные операции) отдельно. [НЕДОДЕЛ-проверка].

---

## 5. [БЕЗОП] Безопасность

### 5.1. `.env` и секреты
- `.gitignore` включает `.env`, `.venv`, `__pycache__`, `*.pyc` — хорошо.
- Проверить, что **нет** закоммиченных секретов: `Create-DB-Neon.py` удалён
  (см. SUMMARY, раздел 7), но рекомендуется ещё раз прогнать
  `git log -S DATABASE_URL` и ротировать пароль Neon, если он когда-либо
  попадал в историю.
- `lib/s3.py` и `lib/db.py` читают `.env` в корне — ок, но `dotenv.load_dotenv(...,
  override=True)` в `s3.load_config` **перезаписывает** уже установленные
  переменные окружения. Это может неожиданно перебить CI-переменные —
  использовать `override=False` (или осознанно). [БЕЗОП]/[МЕЛОЧЬ].

### 5.2. SQL-идентификаторы
Большинство запросов экранируют идентификаторы через `db.quote_ident`, но
**значения** `order` в `crud.list_rows` и `_order_clause` в `view_db.py`
вставляются как текст (см. 4.3). Ограничить источником (белый список).

### 5.3. `service/clear_database.py` — не просмотрен детально
По SUMMARY требует `yes`. Убедиться, что не срабатывает без подтверждения и
не доступно случайно из меню (`run_admin.py` → SERVICE → clear). Отдельно
проверить наличие предохранителя (например, требование ввести имя БД). [НЕДОДЕЛ-проверка].

### 5.4. `upload_media.py` — доверие пользовательскому префиксу пути
`_normalize_custom_dir` защищает от `..`, что хорошо. Но проверки MIME/типа
мягкие (см. 3.5) — потенциальная загрузка `.exe` под видом `doc`. [БЕЗОП]/[НЕДОДЕЛ].

---

## 6. Рассинхронизация документации

- `SUMMARY.txt` раздел 3.5 перечисляет 4 сервисных скрипта; фактически есть
  ещё `backup_snapshot.py`, `restore_snapshot.py` (добавлены в `run_admin.py`).
- `SUMMARY.txt` ссылается на `schema.sql`; в репозитории — `schema.sql.txt`.
- README обещает 7 переменных `.env` — сверить, что документированы все.
- В шапках `media/edit_media.py` («Запуск: python manage_media.py»),
  `media/delete_media.py` («Запуск: python delete_media.py»),
  `db/common/view_db.py` («Запуск: python view_db.py») указаны **старые**
  пути/имена — обновить на новые (`media/edit_media.py` и т.д.).

---

## 7. Рекомендуемый порядок исправлений

1. **[КРИТ]** Транзакция в `service/restore_snapshot.py` (2.3).
2. **[БАГ]** Проверка `None` после `crud.ask_*(required=True)` /
   исправление `ask_*` (2.1, 1.2) — минимум в `create_order-item.py`.
3. **[БАГ]** `os.uname()` → `platform.node()` (1.1).
4. **[БАГ]** Валидация `currency` (длина 3) и `ip` (INET) — 2.7, 2.8.
5. **[БАГ]** Сравнение дат как `datetime` в `create/edit_promo-code.py` (2.6).
6. **Восстановить `schema.sql`** / научить скрипты читать `schema.sql.txt` (3.1).
7. **[БЕЗОП]** `override=False` для dotenv; белый список для `order` (5.1, 4.3).
8. Вынести enum'ы в `lib/enums.py` (4.6); обновить шапки/доки (раздел 6).
9. Дописать недостающий CRUD (`payments`) и тесты (3.4, 3.8).

---

## Приложение A. Перечень просмотренных файлов

> Дерево проекта и назначение каталогов см. в разделе **К.4**; здесь —
> какие конкретно файлы были прочитаны полностью, а какие проверены только
> компиляцией и grep.

Библиотека: `lib/__init__.py`, `lib/db.py`, `lib/ui.py`, `lib/crud.py`,
`lib/delete_guard.py`, `lib/s3.py` (частично `lib/bootstrap.py` — по SUMMARY).

Схема: `schema.sql.txt`, `VIDOH.dbml` (ключевые таблицы).

Домены (полностью или выборочно по каждому действию):
`db/common/view_db.py`, `s3/common/*` (частично), `events/*` (create_event,
create_event-link, create_event-schedule, create_event-document, edit_event,
delete_event, manage_event-categories, manage_event-organizers,
manage_event-media), `catalog/*` (create/edit city, venue, country),
`sales/*` (create_order, create_order-item, edit_order, edit_order-item,
edit_issued-ticket-status, create_issued-ticket), `tickets/*`
(create_ticket, edit_ticket, create_promo-code), `users/*` (create_user,
manage_user-sessions, manage_user-favorites), `organizers/*`
(edit_organizer, manage_organizer-contacts), `reviews/moderate_reviews.py`,
`media/*` (upload, edit, delete), `service/*` (backup_snapshot,
restore_snapshot), `run_admin.py`.

Не прочитаны целиком (но покрыты компиляцией и grep): `events/view_*`,
`events/edit/delete_* event-link/schedule/document`, `catalog/delete_*`,
`catalog/view_*`, `sales/view_*`, `sales/delete_*`, `tickets/view/delete_*`,
`users/view/delete_user`, `organizers/view/create/delete_*`,
`reviews/view_reviews.py`, `reviews/delete_review.py`,
`service/convert_dbml-to-sql.py`, `service/deploy_schema.py`,
`service/clear_database.py`, `service/test_db-connection.py`,
`s3/common/view_s3-storage.py`, `s3/common/sync_media-db-s3.py`,
`lib/bootstrap.py`.
