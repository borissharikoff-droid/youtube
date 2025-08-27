import sqlite3
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер базы данных с поддержкой миграций и индексирования"""
    
    def __init__(self, db_path: str = "youtube_tracker.db"):
        self.db_path = db_path
        self.current_version = 3  # Текущая версия схемы
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Получает соединение с базой данных"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Для удобного доступа к столбцам
        return conn
    
    def init_database(self):
        """Инициализирует базу данных и выполняет миграции"""
        with self.get_connection() as conn:
            # Создаем таблицу версий, если не существует
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_versions (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            
            # Получаем текущую версию
            current_version = self._get_current_version(conn)
            
            # Выполняем миграции
            self._run_migrations(conn, current_version)
    
    def _get_current_version(self, conn: sqlite3.Connection) -> int:
        """Получает текущую версию схемы"""
        cursor = conn.execute("SELECT MAX(version) as version FROM schema_versions")
        result = cursor.fetchone()
        return result['version'] if result['version'] is not None else 0
    
    def _run_migrations(self, conn: sqlite3.Connection, from_version: int):
        """Выполняет миграции с указанной версии"""
        migrations = {
            1: self._migration_v1_initial_schema,
            2: self._migration_v2_add_historical_data,
            3: self._migration_v3_add_indexes_and_optimization
        }
        
        for version in range(from_version + 1, self.current_version + 1):
            if version in migrations:
                logger.info(f"Выполняется миграция до версии {version}")
                migrations[version](conn)
                
                # Записываем версию
                conn.execute(
                    "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
                    (version, f"Migration to version {version}")
                )
                conn.commit()
                logger.info(f"Миграция до версии {version} завершена")
    
    def _migration_v1_initial_schema(self, conn: sqlite3.Connection):
        """Миграция v1: Создание базовых таблиц"""
        
        # Таблица пользователей и их запросов
        conn.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица запросов пользователей
        conn.execute("""
            CREATE TABLE user_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                api_quota_used INTEGER DEFAULT 1,
                response_time_ms INTEGER,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица каналов
        conn.execute("""
            CREATE TABLE channels (
                channel_id TEXT PRIMARY KEY,
                channel_name TEXT NOT NULL,
                username TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Таблица статистики каналов
        conn.execute("""
            CREATE TABLE channel_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subscriber_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                video_count INTEGER DEFAULT 0,
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
            )
        """)
        
        # Таблица видео
        conn.execute("""
            CREATE TABLE videos (
                video_id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                published_at TIMESTAMP NOT NULL,
                duration INTEGER,
                is_scheduled BOOLEAN DEFAULT FALSE,
                scheduled_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
            )
        """)
        
        # Таблица статистики видео
        conn.execute("""
            CREATE TABLE video_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                FOREIGN KEY (video_id) REFERENCES videos (video_id)
            )
        """)
        
        # Таблица комментариев
        conn.execute("""
            CREATE TABLE comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                comment_text TEXT NOT NULL,
                published_at TIMESTAMP NOT NULL,
                like_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (video_id)
            )
        """)
        
        # Таблица кэша
        conn.execute("""
            CREATE TABLE cache (
                cache_key TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """)
        
        # Таблица API квоты
        conn.execute("""
            CREATE TABLE api_quota (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                quota_used INTEGER DEFAULT 0,
                quota_limit INTEGER DEFAULT 10000,
                reset_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def _migration_v2_add_historical_data(self, conn: sqlite3.Connection):
        """Миграция v2: Добавление таблиц для исторических данных"""
        
        # Таблица ежедневной агрегированной статистики каналов
        conn.execute("""
            CREATE TABLE daily_channel_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                date DATE NOT NULL,
                videos_uploaded INTEGER DEFAULT 0,
                videos_scheduled INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                subscriber_growth INTEGER DEFAULT 0,
                view_growth INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id),
                UNIQUE(channel_id, date)
            )
        """)
        
        # Таблица трендов и аналитики
        conn.execute("""
            CREATE TABLE trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL, -- 'channel' or 'video'
                entity_id TEXT NOT NULL,
                metric_name TEXT NOT NULL, -- 'views', 'likes', 'comments', 'subscribers'
                date DATE NOT NULL,
                current_value INTEGER NOT NULL,
                previous_value INTEGER DEFAULT 0,
                growth_absolute INTEGER DEFAULT 0,
                growth_percentage REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица событий (для аудита)
        conn.execute("""
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                user_id INTEGER,
                description TEXT,
                metadata TEXT, -- JSON с дополнительными данными
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
    
    def _migration_v3_add_indexes_and_optimization(self, conn: sqlite3.Connection):
        """Миграция v3: Добавление индексов для оптимизации"""
        
        # Индексы для производительности
        indexes = [
            # Пользователи и запросы
            "CREATE INDEX IF NOT EXISTS idx_user_requests_user_id ON user_requests(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_requests_timestamp ON user_requests(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_user_requests_type ON user_requests(request_type)",
            
            # Каналы
            "CREATE INDEX IF NOT EXISTS idx_channels_active ON channels(active)",
            "CREATE INDEX IF NOT EXISTS idx_channels_updated ON channels(updated_at)",
            
            # Статистика каналов
            "CREATE INDEX IF NOT EXISTS idx_channel_stats_channel_id ON channel_stats(channel_id)",
            "CREATE INDEX IF NOT EXISTS idx_channel_stats_timestamp ON channel_stats(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_channel_stats_channel_time ON channel_stats(channel_id, timestamp)",
            
            # Видео
            "CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id)",
            "CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at)",
            "CREATE INDEX IF NOT EXISTS idx_videos_scheduled ON videos(is_scheduled)",
            "CREATE INDEX IF NOT EXISTS idx_videos_channel_published ON videos(channel_id, published_at)",
            
            # Статистика видео
            "CREATE INDEX IF NOT EXISTS idx_video_stats_video_id ON video_stats(video_id)",
            "CREATE INDEX IF NOT EXISTS idx_video_stats_timestamp ON video_stats(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_video_stats_video_time ON video_stats(video_id, timestamp)",
            
            # Комментарии
            "CREATE INDEX IF NOT EXISTS idx_comments_video_id ON comments(video_id)",
            "CREATE INDEX IF NOT EXISTS idx_comments_published_at ON comments(published_at)",
            
            # Кэш
            "CREATE INDEX IF NOT EXISTS idx_cache_type ON cache(data_type)",
            "CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)",
            
            # Ежедневная статистика
            "CREATE INDEX IF NOT EXISTS idx_daily_stats_channel_date ON daily_channel_stats(channel_id, date)",
            "CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_channel_stats(date)",
            
            # Тренды
            "CREATE INDEX IF NOT EXISTS idx_trends_entity ON trends(entity_type, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_trends_date ON trends(date)",
            "CREATE INDEX IF NOT EXISTS idx_trends_metric ON trends(metric_name, date)",
            
            # События
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_type, entity_id)",
            
            # API квота
            "CREATE INDEX IF NOT EXISTS idx_api_quota_date ON api_quota(date)"
        ]
        
        for index_sql in indexes:
            conn.execute(index_sql)
        
        # Добавляем поля для оптимизации
        try:
            conn.execute("ALTER TABLE cache ADD COLUMN ttl_seconds INTEGER DEFAULT 1800")
        except sqlite3.OperationalError:
            pass  # Поле уже существует
        
        try:
            conn.execute("ALTER TABLE user_requests ADD COLUMN ip_address TEXT")
        except sqlite3.OperationalError:
            pass
    
    def cleanup_expired_cache(self):
        """Очищает устаревший кэш"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM cache WHERE expires_at < CURRENT_TIMESTAMP")
            conn.commit()
    
    def vacuum_database(self):
        """Оптимизирует базу данных"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Получает статистику базы данных"""
        with self.get_connection() as conn:
            stats = {}
            
            # Размер базы данных
            if os.path.exists(self.db_path):
                stats['file_size_mb'] = round(os.path.getsize(self.db_path) / 1024 / 1024, 2)
            
            # Количество записей в таблицах
            tables = ['users', 'user_requests', 'channels', 'channel_stats', 
                     'videos', 'video_stats', 'comments', 'cache', 'daily_channel_stats', 'trends']
            
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
                stats[f'{table}_count'] = cursor.fetchone()['count']
            
            # Статистика кэша
            cursor = conn.execute("SELECT COUNT(*) as count FROM cache WHERE expires_at > CURRENT_TIMESTAMP")
            stats['active_cache_count'] = cursor.fetchone()['count']
            
            cursor = conn.execute("SELECT COUNT(*) as count FROM cache WHERE expires_at <= CURRENT_TIMESTAMP")
            stats['expired_cache_count'] = cursor.fetchone()['count']
            
            # Версия схемы
            cursor = conn.execute("SELECT MAX(version) as version FROM schema_versions")
            stats['schema_version'] = cursor.fetchone()['version']
            
            return stats

class DatabaseRequestTracker:
    """Трекер запросов на основе базы данных"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.daily_request_limit = 15
        self.request_cooldown = 120  # 2 минуты
        self.api_quota_limit = 10000
    
    def can_make_request(self, user_id: int) -> Tuple[bool, str]:
        """Проверяет, может ли пользователь сделать запрос"""
        with self.db.get_connection() as conn:
            # Обеспечиваем существование пользователя
            self._ensure_user_exists(conn, user_id)
            
            # Проверяем дневной лимит
            today = datetime.now().date()
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM user_requests 
                WHERE user_id = ? AND DATE(timestamp) = ? AND success = TRUE
            """, (user_id, today))
            
            requests_today = cursor.fetchone()['count']
            
            if requests_today >= self.daily_request_limit:
                return False, f"Достигнут лимит запросов ({self.daily_request_limit}/день). Попробуйте завтра."
            
            # Проверяем кулдаун
            cursor = conn.execute("""
                SELECT timestamp 
                FROM user_requests 
                WHERE user_id = ? AND success = TRUE
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (user_id,))
            
            last_request = cursor.fetchone()
            if last_request:
                last_time = datetime.fromisoformat(last_request['timestamp'])
                time_diff = (datetime.now() - last_time).total_seconds()
                
                if time_diff < self.request_cooldown:
                    remaining = self.request_cooldown - int(time_diff)
                    minutes = remaining // 60
                    seconds = remaining % 60
                    return False, f"Подождите {minutes}:{seconds:02d} перед следующим запросом."
            
            # Проверяем общую API квоту
            cursor = conn.execute("""
                SELECT quota_used, quota_limit 
                FROM api_quota 
                WHERE date = ?
            """, (today,))
            
            quota_info = cursor.fetchone()
            if quota_info and quota_info['quota_used'] >= quota_info['quota_limit']:
                return False, "Превышен дневной лимит API квоты. Попробуйте завтра."
            
            return True, "OK"
    
    def record_request(self, user_id: int, request_type: str, api_quota_used: int = 1, 
                      response_time_ms: int = None, success: bool = True, error_message: str = None):
        """Записывает запрос пользователя"""
        with self.db.get_connection() as conn:
            # Записываем запрос
            conn.execute("""
                INSERT INTO user_requests 
                (user_id, request_type, api_quota_used, response_time_ms, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, request_type, api_quota_used, response_time_ms, success, error_message))
            
            # Обновляем API квоту
            today = datetime.now().date()
            conn.execute("""
                INSERT INTO api_quota (date, quota_used, quota_limit) 
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET 
                    quota_used = quota_used + ?
            """, (today, api_quota_used, self.api_quota_limit, api_quota_used))
            
            # Обновляем активность пользователя
            conn.execute("""
                UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику пользователя"""
        with self.db.get_connection() as conn:
            today = datetime.now().date()
            
            # Запросы сегодня
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM user_requests 
                WHERE user_id = ? AND DATE(timestamp) = ? AND success = TRUE
            """, (user_id, today))
            requests_today = cursor.fetchone()['count']
            
            # API квота
            cursor = conn.execute("""
                SELECT quota_used, quota_limit 
                FROM api_quota 
                WHERE date = ?
            """, (today,))
            quota_info = cursor.fetchone()
            quota_used = quota_info['quota_used'] if quota_info else 0
            quota_limit = quota_info['quota_limit'] if quota_info else self.api_quota_limit
            
            return {
                'requests_today': requests_today,
                'requests_limit': self.daily_request_limit,
                'remaining_requests': self.daily_request_limit - requests_today,
                'api_quota_used': quota_used,
                'api_quota_limit': quota_limit
            }
    
    def _ensure_user_exists(self, conn: sqlite3.Connection, user_id: int):
        """Обеспечивает существование пользователя в БД"""
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id) VALUES (?)
        """, (user_id,))

class DatabaseCache:
    """Кэш на основе базы данных"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.default_ttl = {
            'channel_stats': 3600,    # 1 час
            'videos': 900,            # 15 минут
            'comments': 1800,         # 30 минут
            'search': 600             # 10 минут
        }
    
    def get(self, key: str, data_type: str = 'default') -> Optional[Any]:
        """Получает данные из кэша"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT data FROM cache 
                WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
            """, (key,))
            
            result = cursor.fetchone()
            if result:
                try:
                    return json.loads(result['data'])
                except json.JSONDecodeError:
                    return None
            return None
    
    def set(self, key: str, data: Any, data_type: str = 'default', ttl: int = None):
        """Сохраняет данные в кэш"""
        if ttl is None:
            ttl = self.default_ttl.get(data_type, 1800)
        
        expires_at = datetime.now() + timedelta(seconds=ttl)
        data_json = json.dumps(data, default=str)
        
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache 
                (cache_key, data_type, data, expires_at)
                VALUES (?, ?, ?, ?)
            """, (key, data_type, data_json, expires_at))
            conn.commit()
    
    def delete(self, key: str):
        """Удаляет данные из кэша"""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
            conn.commit()
    
    def clear_expired(self):
        """Очищает устаревший кэш"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM cache WHERE expires_at <= CURRENT_TIMESTAMP")
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Получает статистику кэша"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    data_type,
                    COUNT(*) as count,
                    SUM(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 ELSE 0 END) as active_count
                FROM cache 
                GROUP BY data_type
            """)
            
            stats_by_type = {}
            for row in cursor.fetchall():
                stats_by_type[row['data_type']] = {
                    'total': row['count'],
                    'active': row['active_count']
                }
            
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 ELSE 0 END) as expired
                FROM cache
            """)
            
            overall = cursor.fetchone()
            
            return {
                'overall': dict(overall),
                'by_type': stats_by_type
            }
