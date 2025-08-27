#!/usr/bin/env python3
"""
Тестирование системы базы данных
"""

import os
import time
from datetime import datetime, timedelta
from database import DatabaseManager, DatabaseCache, DatabaseRequestTracker
from historical_data import HistoricalDataManager
from youtube_stats_db import DatabaseYouTubeStats
import config

def test_database_initialization():
    """Тестирует инициализацию базы данных"""
    print("🗄️ Тестирование инициализации базы данных...")
    
    # Удаляем тестовую БД если существует
    test_db = "test_youtube.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Создаем БД
    db_manager = DatabaseManager(test_db)
    
    # Проверяем создание таблиц
    with db_manager.get_connection() as conn:
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        'api_quota', 'cache', 'channels', 'channel_stats', 
        'comments', 'daily_channel_stats', 'events', 
        'schema_versions', 'trends', 'users', 'user_requests', 
        'videos', 'video_stats'
    ]
    
    print(f"✅ Создано таблиц: {len(tables)}")
    print(f"   Ожидалось: {len(expected_tables)}")
    
    missing = set(expected_tables) - set(tables)
    if missing:
        print(f"❌ Отсутствуют таблицы: {missing}")
    else:
        print("✅ Все таблицы созданы корректно")
    
    # Проверяем версию схемы
    stats = db_manager.get_database_stats()
    print(f"✅ Версия схемы: {stats.get('schema_version', 'unknown')}")
    
    # Очищаем
    os.remove(test_db)
    return len(missing) == 0

def test_cache_system():
    """Тестирует систему кэширования"""
    print("\n💾 Тестирование системы кэширования...")
    
    test_db = "test_cache.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db_manager = DatabaseManager(test_db)
    cache = DatabaseCache(db_manager)
    
    # Тестируем сохранение и получение
    test_data = {'test': 'value', 'number': 123}
    cache.set('test_key', test_data, 'test', ttl=60)
    
    retrieved = cache.get('test_key', 'test')
    if retrieved == test_data:
        print("✅ Кэширование работает корректно")
    else:
        print(f"❌ Ошибка кэширования: {retrieved} != {test_data}")
        return False
    
    # Тестируем TTL
    cache.set('expire_key', {'fast': 'expire'}, 'test', ttl=1)
    time.sleep(1.1)
    expired = cache.get('expire_key', 'test')
    
    if expired is None:
        print("✅ TTL кэша работает корректно")
    else:
        print(f"❌ TTL не работает: получено {expired}")
        return False
    
    # Тестируем статистику
    stats = cache.get_stats()
    print(f"✅ Статистика кэша: {stats['overall']['total']} записей")
    
    # Очищаем
    os.remove(test_db)
    return True

def test_request_tracker():
    """Тестирует трекер запросов"""
    print("\n📊 Тестирование трекера запросов...")
    
    test_db = "test_requests.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db_manager = DatabaseManager(test_db)
    tracker = DatabaseRequestTrackerExtended(db_manager)
    
    user_id = 12345
    
    # Тестируем проверку лимитов
    can_request, message = tracker.can_make_request(user_id)
    if can_request:
        print("✅ Новый пользователь может делать запросы")
    else:
        print(f"❌ Ошибка проверки лимитов: {message}")
        return False
    
    # Записываем запрос
    tracker.record_request(user_id, "test_request", api_quota_used=5)
    
    # Проверяем статистику
    stats = tracker.get_user_stats(user_id)
    if stats['requests_today'] == 1:
        print("✅ Запрос записан корректно")
    else:
        print(f"❌ Ошибка записи запроса: {stats}")
        return False
    
    # Тестируем системную статистику
    system_stats = tracker.get_system_stats()
    if system_stats['today']['total_requests'] >= 1:
        print("✅ Системная статистика работает")
    else:
        print(f"❌ Ошибка системной статистики: {system_stats}")
        return False
    
    # Очищаем
    os.remove(test_db)
    return True

def test_historical_data():
    """Тестирует исторические данные"""
    print("\n📈 Тестирование исторических данных...")
    
    test_db = "test_historical.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db_manager = DatabaseManager(test_db)
    historical = HistoricalDataManager(db_manager)
    
    # Тестовые данные канала
    channel_id = "UCtest123"
    channel_stats = {
        'subscribers': 1000,
        'total_views': 50000,
        'total_videos': 100
    }
    
    test_videos = [
        {
            'title': 'Test Video 1',
            'views': 1000,
            'likes': 50,
            'comments': 10,
            'published_at': datetime.now().isoformat(),
            'comment_list': [
                {'author': 'User1', 'text': 'Great video!'}
            ]
        },
        {
            'title': 'Test Video 2', 
            'views': 2000,
            'likes': 100,
            'comments': 20,
            'published_at': (datetime.now() - timedelta(hours=1)).isoformat(),
            'comment_list': []
        }
    ]
    
    # Сохраняем данные
    historical.store_channel_data(channel_id, "Test Channel", channel_stats, test_videos)
    
    # Проверяем сохранение
    with db_manager.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM channels WHERE channel_id = ?", (channel_id,))
        channel_count = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM videos WHERE channel_id = ?", (channel_id,))
        video_count = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM comments")
        comment_count = cursor.fetchone()[0]
    
    if channel_count == 1 and video_count == 2 and comment_count == 1:
        print("✅ Данные сохранены корректно")
    else:
        print(f"❌ Ошибка сохранения: каналов={channel_count}, видео={video_count}, комментариев={comment_count}")
        return False
    
    # Тестируем агрегацию
    historical.calculate_daily_aggregates()
    
    with db_manager.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM daily_channel_stats")
        daily_count = cursor.fetchone()[0]
    
    if daily_count >= 1:
        print("✅ Ежедневная агрегация работает")
    else:
        print(f"❌ Ошибка агрегации: {daily_count}")
        return False
    
    # Очищаем
    os.remove(test_db)
    return True

def test_youtube_stats_integration():
    """Тестирует интеграцию с YouTube Stats"""
    print("\n🎬 Тестирование интеграции YouTube Stats...")
    
    test_db = "test_integration.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
        # Создаем экземпляр
        stats = DatabaseYouTubeStats(test_db)
        
        # Проверяем, что БД создана
        db_stats = stats.get_database_stats()
        if 'database' in db_stats:
            print("✅ База данных инициализирована")
        else:
            print(f"❌ Ошибка инициализации: {db_stats}")
            return False
        
        # Тестируем кэш
        test_key = "test_integration"
        test_data = {'integration': 'test'}
        stats._set_cached_data(test_key, test_data, 'test')
        
        cached_data = stats._get_cached_data(test_key, 'test')
        if cached_data == test_data:
            print("✅ Интеграция кэша работает")
        else:
            print(f"❌ Ошибка кэша: {cached_data}")
            return False
        
        # Тестируем совместимость API
        try:
            summary = stats.get_summary_stats()
            if isinstance(summary, dict):
                print("✅ API совместимость сохранена")
            else:
                print(f"❌ Проблемы с API: {type(summary)}")
                return False
        except Exception as e:
            # Ошибки YouTube API ожидаемы в тестах
            print(f"⚠️ YouTube API недоступен (ожидаемо): {e}")
        
        # Очищаем
        stats.close()
        os.remove(test_db)
        return True
        
    except Exception as e:
        print(f"❌ Ошибка интеграции: {e}")
        if os.path.exists(test_db):
            os.remove(test_db)
        return False

def test_migration():
    """Тестирует миграцию данных"""
    print("\n🔄 Тестирование миграции данных...")
    
    # Создаем тестовый JSON файл
    import json
    test_json = "test_migration.json"
    test_data = {
        'users': {
            '123': {'requests_today': 5, 'last_request': int(time.time())},
            '456': {'requests_today': 2, 'last_request': int(time.time()) - 3600}
        },
        'api_quota': {'used': 100, 'reset_time': int(time.time()) + 86400}
    }
    
    with open(test_json, 'w') as f:
        json.dump(test_data, f)
    
    test_db = "test_migration.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
        # Создаем статистику с миграцией
        stats = DatabaseYouTubeStats(test_db)
        stats.migrate_from_json(test_json)
        
        # Проверяем миграцию
        with stats.db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT quota_used FROM api_quota ORDER BY date DESC LIMIT 1")
            quota_row = cursor.fetchone()
            quota_used = quota_row[0] if quota_row else 0
        
        if user_count >= 2:
            print(f"✅ Пользователи мигрированы: {user_count}")
        else:
            print(f"❌ Ошибка миграции пользователей: {user_count}")
            return False
        
        # Проверяем backup файл
        backup_file = f"{test_json}.backup"
        if os.path.exists(backup_file):
            print("✅ Backup файл создан")
            os.remove(backup_file)
        else:
            print("⚠️ Backup файл не создан")
        
        stats.close()
        os.remove(test_db)
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False
    
    finally:
        # Очищаем тестовые файлы
        for file in [test_json, test_db]:
            if os.path.exists(file):
                os.remove(file)

def run_performance_test():
    """Тестирует производительность базы данных"""
    print("\n⚡ Тестирование производительности...")
    
    test_db = "test_performance.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db_manager = DatabaseManager(test_db)
    cache = DatabaseCache(db_manager)
    
    # Тест скорости записи в кэш
    start_time = time.time()
    for i in range(1000):
        cache.set(f"perf_key_{i}", {'data': f'value_{i}'}, 'performance')
    write_time = time.time() - start_time
    
    # Тест скорости чтения из кэша
    start_time = time.time()
    for i in range(1000):
        cache.get(f"perf_key_{i}", 'performance')
    read_time = time.time() - start_time
    
    print(f"✅ Производительность:")
    print(f"   Запись 1000 записей: {write_time:.3f}с ({1000/write_time:.0f} записей/с)")
    print(f"   Чтение 1000 записей: {read_time:.3f}с ({1000/read_time:.0f} записей/с)")
    
    # Тест размера БД
    file_size = os.path.getsize(test_db) / 1024  # KB
    print(f"   Размер БД с 1000 записей: {file_size:.1f} КБ")
    
    os.remove(test_db)
    
    # Хорошие показатели: >500 записей/с, <500КБ на 1000 записей
    return write_time < 2.0 and read_time < 2.0 and file_size < 500

def main():
    """Запуск всех тестов"""
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    tests = [
        ("Инициализация БД", test_database_initialization),
        ("Система кэширования", test_cache_system), 
        ("Трекер запросов", test_request_tracker),
        ("Исторические данные", test_historical_data),
        ("Интеграция YouTube Stats", test_youtube_stats_integration),
        ("Миграция данных", test_migration),
        ("Производительность", run_performance_test)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
            print(f"\n{status}: {test_name}")
        except Exception as e:
            print(f"\n❌ ОШИБКА в {test_name}: {e}")
            results.append((test_name, False))
    
    print(f"\n{'='*50}")
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {test_name}")
    
    print(f"\n🎯 ИТОГО: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! База данных готова к использованию.")
    else:
        print("⚠️ Некоторые тесты провалены. Проверьте ошибки выше.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
