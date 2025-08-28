#!/usr/bin/env python3
"""
Тест бота для Railway деплоя
"""

import os
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Тестирует импорты всех модулей"""
    try:
        logger.info("🔍 Тестирование импортов...")
        
        # Устанавливаем переменную для Railway режима
        os.environ["RAILWAY_STATIC_URL"] = "test"
        
        # Тестируем основные импорты
        import config_railway as config
        logger.info("✅ config_railway импортирован")
        
        from database import DatabaseManager, DatabaseCache, DatabaseRequestTracker
        logger.info("✅ database модули импортированы")
        
        from historical_data import HistoricalDataManager
        logger.info("✅ historical_data импортирован")
        
        from youtube_stats_db import DatabaseYouTubeStats
        logger.info("✅ youtube_stats_db импортирован")
        
        from request_tracker_db import DatabaseRequestTrackerExtended
        logger.info("✅ request_tracker_db импортирован")
        
        logger.info("✅ Все импорты прошли успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        return False

def test_config():
    """Тестирует конфигурацию"""
    try:
        logger.info("🔧 Тестирование конфигурации...")
        
        # Устанавливаем тестовые переменные окружения
        os.environ["TELEGRAM_TOKEN"] = "test_token"
        os.environ["YOUTUBE_API_KEY"] = "test_api_key"
        os.environ["ADMIN_ID"] = "250800600"
        
        import config_railway as config
        
        # Проверяем основные настройки
        assert hasattr(config, 'TELEGRAM_TOKEN')
        assert hasattr(config, 'YOUTUBE_API_KEY')
        assert hasattr(config, 'ADMIN_ID')
        assert hasattr(config, 'CHANNELS')
        assert hasattr(config, 'DATABASE_PATH')
        
        logger.info(f"✅ TELEGRAM_TOKEN: {'Set' if config.TELEGRAM_TOKEN else 'Not set'}")
        logger.info(f"✅ YOUTUBE_API_KEY: {'Set' if config.YOUTUBE_API_KEY else 'Not set'}")
        logger.info(f"✅ ADMIN_ID: {config.ADMIN_ID}")
        logger.info(f"✅ Каналов для мониторинга: {len(config.CHANNELS)}")
        logger.info(f"✅ DATABASE_PATH: {config.DATABASE_PATH}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка конфигурации: {e}")
        return False

def test_database():
    """Тестирует базу данных"""
    try:
        logger.info("💾 Тестирование базы данных...")
        
        from database import DatabaseManager
        
        # Создаем временную БД
        test_db_path = "/tmp/test_youtube_tracker.db"
        db = DatabaseManager(test_db_path)
        
        # Проверяем статистику БД
        stats = db.get_database_stats()
        logger.info(f"✅ База данных создана, версия схемы: {stats.get('schema_version', 'Unknown')}")
        logger.info(f"✅ Размер БД: {stats.get('file_size_mb', 0)} МБ")
        
        # Очищаем тестовую БД
        import os
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка базы данных: {e}")
        return False

def test_bot_initialization():
    """Тестирует инициализацию бота"""
    try:
        logger.info("🤖 Тестирование инициализации бота...")
        
        # Устанавливаем тестовые переменные окружения
        os.environ["TELEGRAM_TOKEN"] = "test_token"
        os.environ["YOUTUBE_API_KEY"] = "test_api_key"
        
        from youtube_stats_db import DatabaseYouTubeStats
        from request_tracker_db import DatabaseRequestTrackerExtended
        from database import DatabaseManager
        
        # Создаем временную БД для теста
        test_db_path = "/tmp/test_bot_youtube_tracker.db"
        db_manager = DatabaseManager(test_db_path)
        
        # Инициализируем компоненты
        youtube_stats = DatabaseYouTubeStats(test_db_path)
        request_tracker = DatabaseRequestTrackerExtended(db_manager)
        
        logger.info("✅ YouTubeStats инициализирован")
        logger.info("✅ RequestTracker инициализирован")
        
        # Очищаем тестовую БД
        import os
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        return False

def main():
    """Основная функция тестирования"""
    logger.info("🚀 Запуск тестирования Railway деплоя")
    logger.info("=" * 50)
    
    tests = [
        ("Импорты", test_imports),
        ("Конфигурация", test_config),
        ("База данных", test_database),
        ("Инициализация бота", test_bot_initialization)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Тест: {test_name}")
        logger.info("-" * 30)
        
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name}: ПРОШЕЛ")
        else:
            logger.error(f"❌ {test_name}: ПРОВАЛИЛСЯ")
    
    logger.info("\n" + "=" * 50)
    logger.info(f"📊 Результаты тестирования: {passed}/{total} тестов прошли")
    
    if passed == total:
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Бот готов к деплою на Railway.")
        return True
    else:
        logger.error(f"❌ {total - passed} тестов провалились. Необходимы исправления.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
