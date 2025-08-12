#!/usr/bin/env python3
"""
Миграции для базы данных Kapital Sheet Bot
"""

import psycopg2
import logging
from environs import Env

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
env = Env()
env.read_env()

def get_db_conn():
    """Получение соединения с базой данных"""
    return psycopg2.connect(
        dbname=env.str('POSTGRES_DB', 'kapital'),
        user=env.str('POSTGRES_USER', 'postgres'),
        password=env.str('POSTGRES_PASSWORD', 'postgres'),
        host=env.str('POSTGRES_HOST', 'localhost'),
        port=env.str('POSTGRES_PORT', '5432')
    )

def create_migrations_table():
    """Создание таблицы для отслеживания миграций"""
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS migrations (
            id SERIAL PRIMARY KEY,
            migration_name TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        logger.info("Таблица migrations создана/проверена")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы migrations: {e}")
        conn.rollback()
    finally:
        conn.close()

def is_migration_applied(migration_name):
    """Проверка, применена ли миграция"""
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        c.execute('SELECT COUNT(*) FROM migrations WHERE migration_name = %s', (migration_name,))
        count = c.fetchone()[0]
        return count > 0
    except Exception as e:
        logger.error(f"Ошибка при проверке миграции {migration_name}: {e}")
        return False
    finally:
        conn.close()

def mark_migration_applied(migration_name):
    """Отметить миграцию как примененную"""
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        c.execute('INSERT INTO migrations (migration_name) VALUES (%s)', (migration_name,))
        conn.commit()
        logger.info(f"Миграция {migration_name} отмечена как примененная")
    except Exception as e:
        logger.error(f"Ошибка при отметке миграции {migration_name}: {e}")
        conn.rollback()
    finally:
        conn.close()

def migration_001_initial_schema():
    """Миграция 001: Создание базовой структуры"""
    migration_name = "001_initial_schema"
    
    if is_migration_applied(migration_name):
        logger.info(f"Миграция {migration_name} уже применена")
        return
    
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        # Создание таблиц
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            name TEXT,
            phone TEXT,
            status TEXT,
            reg_date TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS objects (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS category_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            user_name TEXT,
            category_name TEXT,
            status TEXT DEFAULT 'pending',
            request_date TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS object_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            user_name TEXT,
            object_name TEXT,
            status TEXT DEFAULT 'pending',
            request_date TEXT
        )''')
        
        conn.commit()
        mark_migration_applied(migration_name)
        logger.info(f"Миграция {migration_name} успешно применена")
        
    except Exception as e:
        logger.error(f"Ошибка при применении миграции {migration_name}: {e}")
        conn.rollback()
    finally:
        conn.close()

def migration_002_default_categories():
    """Миграция 002: Добавление категорий по умолчанию"""
    migration_name = "002_default_categories"
    
    if is_migration_applied(migration_name):
        logger.info(f"Миграция {migration_name} уже применена")
        return
    
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        # Проверяем, есть ли уже категории
        c.execute('SELECT COUNT(*) FROM categories')
        if c.fetchone()[0] == 0:
            # Добавляем новые категории
            categories = [
                "Мижозлардан", "Аренда техника и инструменты", "Бетон тайёрлаб бериш", 
                "Геология ва лойиха ишлари", "Геология ишлари", "Диз топливо для техники", 
                "Дорожные расходы", "Заправка", "Коммунал и интернет", "Кунлик ишчи", 
                "Объем усталар", "Перевод", "Ойлик ишчилар", "Олиб чикиб кетилган мусор", 
                "Перечесления Расход", "Питание", "Прочие расходы", "Ремонт техники и запчасти", 
                "Сотиб олинган материал", "Карз", "Сотиб олинган снос уйлар", "Валюта операция", 
                "Хизмат (Прочие расходы)", "Хоз товары и инвентарь", "Хожи Ака", "Эхсон", "Хомийлик"
            ]
            
            for name in categories:
                try:
                    c.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
                except psycopg2.IntegrityError:
                    # Категория уже существует, пропускаем
                    pass
            
            logger.info(f"Добавлено {len(categories)} категорий")
        
        conn.commit()
        mark_migration_applied(migration_name)
        logger.info(f"Миграция {migration_name} успешно применена")
        
    except Exception as e:
        logger.error(f"Ошибка при применении миграции {migration_name}: {e}")
        conn.rollback()
    finally:
        conn.close()

def migration_003_default_objects():
    """Миграция 003: Добавление объектов по умолчанию"""
    migration_name = "003_default_objects"
    
    if is_migration_applied(migration_name):
        logger.info(f"Миграция {migration_name} уже применена")
        return
    
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        # Проверяем, есть ли уже объекты
        c.execute('SELECT COUNT(*) FROM objects')
        if c.fetchone()[0] == 0:
            # Добавляем новые объекты
            objects = [
                "Сам Сити", "Ургут", "Ал Бухорий", "Ал-Бухорий Хотел", "Рубловка", "Қува ҚВП", 
                "Макон Малл", "Карши Малл", "Воха Гавхари", "Карши Хотел", "Зарметан усто Ғафур", 
                "Кожа завод", "Мотрид катеж", "Хишрав", "Махдуми Азам", "Сирдарё 1/10 Зухри", 
                "Эшонгузар", "Рубловка(Хожи бобо дом)", "Ситй+Сиёб Б Й К блок", "Қўқон малл", 
                "Жиззах мактаб", "Кушработ КВП", "Иштихон КВП", "Кэмпинг", "Бекобод КВП", 
                "Брдомзор", "Схф Данлагер"
            ]
            
            for name in objects:
                try:
                    c.execute('INSERT INTO objects (name) VALUES (%s)', (name,))
                except psycopg2.IntegrityError:
                    # Объект уже существует, пропускаем
                    pass
            
            logger.info(f"Добавлено {len(objects)} объектов")
        
        conn.commit()
        mark_migration_applied(migration_name)
        logger.info(f"Миграция {migration_name} успешно применена")
        
    except Exception as e:
        logger.error(f"Ошибка при применении миграции {migration_name}: {e}")
        conn.rollback()
    finally:
        conn.close()

def run_all_migrations():
    """Запуск всех миграций"""
    logger.info("Начинаем выполнение миграций...")
    
    # Создаем таблицу миграций
    create_migrations_table()
    
    # Применяем миграции по порядку
    migrations = [
        migration_001_initial_schema,
        migration_002_default_categories,
        migration_003_default_objects
    ]
    
    for migration in migrations:
        try:
            migration()
        except Exception as e:
            logger.error(f"Ошибка при выполнении миграции: {e}")
            break
    
    logger.info("Выполнение миграций завершено")

def reset_migrations():
    """Сброс всех миграций (для разработки)"""
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        c.execute('TRUNCATE TABLE migrations RESTART IDENTITY CASCADE')
        conn.commit()
        logger.info("Все миграции сброшены")
    except Exception as e:
        logger.error(f"Ошибка при сбросе миграций: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "migrate":
            run_all_migrations()
        elif command == "reset":
            reset_migrations()
        elif command == "status":
            # Показать статус миграций
            conn = get_db_conn()
            c = conn.cursor()
            c.execute('SELECT migration_name, applied_at FROM migrations ORDER BY id')
            migrations = c.fetchall()
            conn.close()
            
            print("Статус миграций:")
            for migration_name, applied_at in migrations:
                print(f"✅ {migration_name} - {applied_at}")
        else:
            print("Доступные команды:")
            print("  python migrations.py migrate  - выполнить все миграции")
            print("  python migrations.py reset   - сбросить все миграции")
            print("  python migrations.py status  - показать статус миграций")
    else:
        print("Использование: python migrations.py [migrate|reset|status]")
        print("  migrate - выполнить все миграции")
        print("  reset  - сбросить все миграции")
        print("  status - показать статус миграций")
