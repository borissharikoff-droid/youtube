# 💾 База данных YouTube Tracker

## Обзор системы

Полная замена JSON файлов на SQLite базу данных с миграциями, индексированием и историческими данными.

## 🗄️ Архитектура базы данных

### Основные таблицы

#### **Пользователи и запросы**
- `users` - информация о пользователях
- `user_requests` - история запросов с метриками
- `api_quota` - отслеживание квоты API

#### **YouTube данные**
- `channels` - информация о каналах
- `channel_stats` - статистика каналов по времени
- `videos` - информация о видео
- `video_stats` - статистика видео по времени
- `comments` - комментарии к видео

#### **Аналитика и история**
- `daily_channel_stats` - ежедневные агрегаты по каналам
- `trends` - тренды роста для каналов и видео
- `events` - лог системных событий

#### **Система**
- `cache` - кэш с TTL
- `schema_versions` - версионирование миграций

## 🚀 Ключевые возможности

### 1. **Система миграций**
```python
# Автоматические миграции при запуске
db = DatabaseManager()  # Автоматически мигрирует до последней версии

# Текущая версия: v3
# v1: Базовые таблицы
# v2: Исторические данные и аналитика  
# v3: Индексы и оптимизация
```

### 2. **Умное кэширование**
```python
cache = DatabaseCache(db_manager)

# Разные TTL для разных типов данных
cache.set(key, data, 'channel_stats', ttl=3600)  # 1 час
cache.set(key, data, 'videos', ttl=900)          # 15 минут
cache.set(key, data, 'comments', ttl=1800)       # 30 минут
```

### 3. **Исторические данные**
```python
historical = HistoricalDataManager(db_manager)

# Сохранение данных канала
historical.store_channel_data(channel_id, name, stats, videos)

# Вычисление ежедневных агрегатов
historical.calculate_daily_aggregates()

# Анализ трендов
trends = historical.get_channel_trends(channel_id, days=7)
```

### 4. **Расширенная аналитика**
```python
youtube_stats = DatabaseYouTubeStats()

# Аналитический дашборд
dashboard = youtube_stats.get_analytics_dashboard(days=7)

# Топ контент
top_content = historical.get_top_performing_content(days=7)

# Экспорт данных
data = youtube_stats.export_data(start_date, end_date)
```

## 📊 Новые команды бота

### **Основные команды**
- `/start` - Главное меню (обновлено)
- `/stats` - Детальная статистика 
- `/day` - Сводная статистика

### **Новые аналитические команды**
- `/analytics` - Расширенная аналитика за 7 дней
- `/trends` - Тренды роста каналов
- `/quota` - Статистика запросов (обновлено)

### **Админские команды**
- `/dbstats` - Статистика базы данных
- `/help` - Обновленная справка

## 🔧 Компоненты системы

### **DatabaseManager**
```python
# Основной менеджер БД
db = DatabaseManager("youtube_tracker.db")

# Статистика БД
stats = db.get_database_stats()

# Оптимизация
db.vacuum_database()
```

### **DatabaseRequestTracker**
```python
# Трекер запросов на БД
tracker = DatabaseRequestTracker(db_manager)

# Расширенная статистика
activity = tracker.get_user_activity_stats(user_id, days=7)
system_stats = tracker.get_system_stats()
```

### **HistoricalDataManager**
```python
# Управление историческими данными
historical = HistoricalDataManager(db_manager)

# Аналитическая сводка
summary = historical.get_analytics_summary(days=7)

# Очистка старых данных
historical.cleanup_old_data(days_to_keep=90)
```

### **DatabaseYouTubeStats**
```python
# YouTube статистика с БД
stats = DatabaseYouTubeStats()

# Автоматическое сохранение в БД
stats.get_batch_channel_stats(channel_ids)  # Сохраняет в БД

# Аналитика
dashboard = stats.get_analytics_dashboard()
```

## 📈 Производительность

### **Оптимизации**
- **27 индексов** для быстрых запросов
- **Batch операции** для множественных вставок
- **Умное кэширование** с разными TTL
- **Автоматическая очистка** устаревших данных

### **Ожидаемые улучшения**
- Запросы к данным: **10-50x быстрее** чем JSON
- Аналитика: **Новая возможность** 
- Тренды: **Новая возможность**
- Масштабируемость: **Без ограничений**

## 🛠️ Миграция с JSON

### **Автоматическая миграция**
```python
# При первом запуске автоматически мигрируется из:
# - request_data.json → users, user_requests, api_quota
# - last_requests.json → не используется (заменено БД)

stats = DatabaseYouTubeStats()
stats.migrate_from_json()  # Автоматически при инициализации
```

### **Резервные копии**
- JSON файлы переименовываются в `.backup`
- Данные сохраняются для отката
- Миграция безопасна

## 📊 Схема базы данных

```sql
-- Основные отношения
users (1) → (N) user_requests
channels (1) → (N) channel_stats
channels (1) → (N) videos
videos (1) → (N) video_stats
videos (1) → (N) comments

-- Аналитические таблицы
channels (1) → (N) daily_channel_stats
trends (entity_type, entity_id) → channels/videos
```

## 🧪 Тестирование

### **Запуск тестов**
```bash
python3 test_database.py
```

### **Что тестируется**
- ✅ Инициализация БД и миграции
- ✅ Система кэширования с TTL
- ✅ Трекер запросов и лимиты
- ✅ Исторические данные и тренды
- ✅ Интеграция с YouTube Stats
- ✅ Миграция из JSON
- ✅ Производительность операций

## 📈 Мониторинг и аналитика

### **Статистика БД**
```python
# Размер и содержимое
db_stats = db_manager.get_database_stats()

# Статистика кэша
cache_stats = cache.get_stats()

# Системная активность
system_stats = tracker.get_system_stats()
```

### **Ключевые метрики**
- Размер БД в МБ
- Количество записей по таблицам
- Hit rate кэша
- Активность пользователей
- Использование API квоты

## 🔄 Обслуживание

### **Автоматическая очистка**
```python
# Очистка устаревшего кэша
cache.clear_expired()

# Очистка старых данных
historical.cleanup_old_data(days_to_keep=90)

# Оптимизация БД
db_manager.vacuum_database()
```

### **Резервное копирование**
```bash
# Простое копирование файла
cp youtube_tracker.db backup/youtube_tracker_$(date +%Y%m%d).db

# Экспорт данных
python3 -c "
from youtube_stats_db import DatabaseYouTubeStats
stats = DatabaseYouTubeStats()
data = stats.export_data(start_date, end_date)
print(json.dumps(data))
" > export.json
```

## 🚨 Устранение неполадок

### **Проблемы миграции**
```python
# Принудительная пересборка БД
import os
os.remove('youtube_tracker.db')
db = DatabaseManager()  # Создаст заново
```

### **Проблемы производительности**
```python
# Оптимизация БД
db.vacuum_database()

# Очистка кэша
cache.clear_expired()

# Проверка индексов
# Все индексы создаются автоматически в миграции v3
```

### **Откат на JSON**
```python
# В bot.py поменять импорты:
from youtube_stats_optimized import OptimizedYouTubeStats
from request_tracker import RequestTracker

# И инициализацию:
self.youtube_stats = OptimizedYouTubeStats()
self.request_tracker = RequestTracker()
```

## 🎯 Результат

### **Что получили**
✅ **Полнофункциональная БД** с миграциями и индексами  
✅ **Исторические данные** и аналитика трендов  
✅ **Умное кэширование** с разными TTL  
✅ **Расширенная аналитика** в боте  
✅ **Высокая производительность** и масштабируемость  
✅ **Автоматическая миграция** из JSON  
✅ **Полная совместимость** с существующим API  

### **Новые возможности**
- 📈 Тренды роста каналов
- 🏆 Топ контент и аналитика  
- 📊 Исторические графики
- 💾 Эффективное хранение данных
- 🚀 Подготовка к веб-интерфейсу

---

**Система готова к продакшену!** 🚀
