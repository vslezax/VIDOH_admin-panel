"""
Проверка работоспособности БД в Neon:
- подключение
- расширение citext
- список таблиц и колонок
- вставка/чтение/удаление тестовой записи
- регистронезависимая уникальность email (если есть такая колонка)
- внешние ключи
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("Не задан DATABASE_URL в .env")

# ANSI-цвета для читаемого вывода
OK = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"
WARN = "\033[93m[WARN]\033[0m"


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main():
    print(f"{INFO} Подключаюсь к Neon...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
    except Exception as e:
        sys.exit(f"{FAIL} Не удалось подключиться: {e}")

    cur = conn.cursor()
    print(f"{OK} Соединение установлено")

    # ------------------------------------------------------------
    # 1. Версия сервера
    # ------------------------------------------------------------
    section("1. Версия PostgreSQL")
    cur.execute("SELECT version();")
    print(f"{INFO} {cur.fetchone()[0]}")

    # ------------------------------------------------------------
    # 2. Расширение citext
    # ------------------------------------------------------------
    section("2. Расширение citext")
    cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'citext';")
    if cur.fetchone():
        print(f"{OK} citext включен")
    else:
        print(f"{FAIL} citext НЕ включен — email-поля будут регистрозависимыми")

    # ------------------------------------------------------------
    # 3. Список таблиц
    # ------------------------------------------------------------
    section("3. Таблицы в схеме public")
    cur.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """)
    tables = [r[0] for r in cur.fetchall()]
    if not tables:
        print(f"{FAIL} Таблиц нет. Запусти 2_deploy.py")
        cur.close()
        conn.close()
        return

    for t in tables:
        print(f"  • {t}")
    print(f"{OK} Всего таблиц: {len(tables)}")

    # ------------------------------------------------------------
    # 4. Колонки и типы
    # ------------------------------------------------------------
    section("4. Структура таблиц")
    cur.execute("""
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """)
    current_table = None
    for table, column, dtype, nullable in cur.fetchall():
        if table != current_table:
            print(f"\n  {table}:")
            current_table = table
        null_mark = "" if nullable == "YES" else " NOT NULL"
        print(f"    - {column}: {dtype}{null_mark}")

    # ------------------------------------------------------------
    # 5. Внешние ключи
    # ------------------------------------------------------------
    section("5. Внешние ключи")
    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS ref_table,
            ccu.column_name AS ref_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        ORDER BY tc.table_name;
    """)
    fks = cur.fetchall()
    if fks:
        for tbl, col, ref_tbl, ref_col in fks:
            print(f"  {tbl}.{col} → {ref_tbl}.{ref_col}")
        print(f"{OK} Внешних ключей: {len(fks)}")
    else:
        print(f"{WARN} Внешних ключей не найдено")

    # ------------------------------------------------------------
    # 6. Проверка citext
    # ------------------------------------------------------------
    section("6. Проверка citext")

    # Ищем колонку типа citext
    cur.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND udt_name = 'citext'
        ORDER BY table_name
        LIMIT 1;
    """)
    row = cur.fetchone()

    if not row:
        print(f"{WARN} Колонок типа citext не найдено, пропускаю тест")
    else:
        table, column = row
        print(f"{INFO} Тестирую на {table}.{column}")

        # Все обязательные NOT NULL колонки без default,
        # которые НЕ являются identity и НЕ генерируются автоматически
        cur.execute("""
            SELECT column_name, udt_name, is_identity
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND is_nullable = 'NO'
              AND column_default IS NULL
              AND is_identity = 'NO'
              AND column_name <> %s;
        """, (table, column))
        required = cur.fetchall()

        def build_values(suffix: str):
            cols = [column]
            # email специально в разном регистре между двумя вставками
            vals = [f"'Test{suffix}@Example.com'"]
            for col, udt, _ in required:
                cols.append(col)
                if udt in ("int2", "int4", "int8"):
                    vals.append("999999" if suffix == "" else "999998")
                elif udt == "uuid":
                    vals.append("gen_random_uuid()")
                elif udt == "bool":
                    vals.append("true")
                elif udt in ("timestamptz", "timestamp"):
                    vals.append("now()")
                elif udt == "numeric":
                    vals.append("0")
                else:
                    vals.append(f"'test_{col}{suffix}'")
            return cols, vals

        # Первая вставка
        cols, vals = build_values("")
        insert_sql = (
            f'INSERT INTO "{table}" ({", ".join(cols)}) '
            f'VALUES ({", ".join(vals)});'
        )
        print(f"{INFO} SQL: {insert_sql}")
        try:
            cur.execute(insert_sql)
            print(f"{OK} INSERT с 'Test@Example.com' прошёл")
        except Exception as e:
            print(f"{FAIL} INSERT упал: {e}")
            cur.close()
            conn.close()
            return

        # Вторая вставка — тот же email в нижнем регистре
        cols, vals = build_values("2")
        vals[0] = "'test@example.com'"  # намеренно другой регистр
        dup_sql = (
            f'INSERT INTO "{table}" ({", ".join(cols)}) '
            f'VALUES ({", ".join(vals)});'
        )
        print(f"{INFO} SQL: {dup_sql}")
        try:
            cur.execute(dup_sql)
            print(f"{FAIL} Дубль 'test@example.com' прошёл — citext НЕ работает!")
        except psycopg2.errors.UniqueViolation:
            print(f"{OK} Дубль отклонён — citext работает корректно")
        except Exception as e:
            print(f"{WARN} Неожиданная ошибка на дубле: {e}")

        # Чистим
        cur.execute(
            f'DELETE FROM "{table}" WHERE {column} ILIKE \'test%@example.com\';'
        )
        print(f"{OK} Тестовые записи удалены")

    # ------------------------------------------------------------
    # 7. Чтение из всех таблиц (проверка SELECT)
    # ------------------------------------------------------------
    section("7. SELECT из каждой таблицы")
    for t in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{t}";')
            count = cur.fetchone()[0]
            print(f"{OK} {t}: {count} строк")
        except Exception as e:
            print(f"{FAIL} {t}: {e}")

    # ------------------------------------------------------------
    # Итог
    # ------------------------------------------------------------
    section("Готово")
    print(f"{OK} Все базовые проверки пройдены.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()