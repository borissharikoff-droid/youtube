import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import os
# Выбираем конфигурацию в зависимости от среды
if os.getenv("RAILWAY_STATIC_URL"):
    import config_railway as config
else:
    import config
from database import DatabaseManager, DatabaseCache
from historical_data import HistoricalDataManager
from youtube_stats_optimized import OptimizedYouTubeStats

logger = logging.getLogger(__name__)

class DatabaseYouTubeStats(OptimizedYouTubeStats):
    """YouTube статистика с интеграцией базы данных"""
    
    def __init__(self, db_path: str = "youtube_tracker.db"):
        # Инициализируем базу данных
        self.db_manager = DatabaseManager(db_path)
        self.cache = DatabaseCache(self.db_manager)
        self.historical = HistoricalDataManager(self.db_manager)
        
        # Инициализируем родительский класс без его кэша
        super().__init__()
        
        # Заменяем кэш на базу данных
        self._cache = None  # Отключаем файловый кэш
        
        # Очищаем устаревший кэш при старте
        self.cache.clear_expired()
        
        logger.info("DatabaseYouTubeStats initialized with database backend")
    
    def _get_cached_data(self, key: str, data_type: str = 'videos') -> Optional[Dict]:
        """Получает данные из кэша БД"""
        return self.cache.get(key, data_type)
    
    def _set_cached_data(self, key: str, data: Dict, data_type: str = 'videos'):
        """Сохраняет данные в кэш БД"""
        self.cache.set(key, data, data_type)
    
    def get_batch_channel_stats(self, channel_ids: List[str]) -> Dict[str, Dict]:
        """Получает статистику каналов с сохранением в БД"""
        results = super().get_batch_channel_stats(channel_ids)
        
        # Сохраняем результаты в БД для исторических данных
        for channel_id, stats in results.items():
            if stats:
                try:
                    channel_name = next(
                        (c['name'] for c in config.CHANNELS if c['channel_id'] == channel_id),
                        f"Channel_{channel_id}"
                    )
                    
                    with self.db_manager.get_connection() as conn:
                        # Обновляем информацию о канале
                        conn.execute("""
                            INSERT OR REPLACE INTO channels 
                            (channel_id, channel_name, updated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                        """, (channel_id, channel_name))
                        
                        # Сохраняем статистику канала
                        conn.execute("""
                            INSERT INTO channel_stats 
                            (channel_id, subscriber_count, view_count, video_count)
                            VALUES (?, ?, ?, ?)
                        """, (channel_id, stats.get('subscribers', 0), 
                              stats.get('total_views', 0), stats.get('total_videos', 0)))
                        
                        conn.commit()
                        
                except Exception as e:
                    logger.error(f"Error saving channel stats to DB: {e}")
        
        return results
    
    def get_incremental_videos_for_period(self, channel_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Получает видео с сохранением в БД"""
        videos = super().get_incremental_videos_for_period(channel_id, start_date, end_date)
        
        # Сохраняем видео в БД
        if videos:
            try:
                self._save_videos_to_db(channel_id, videos)
            except Exception as e:
                logger.error(f"Error saving videos to DB: {e}")
        
        return videos
    
    def _save_videos_to_db(self, channel_id: str, videos: List[Dict]):
        """Сохраняет видео в базу данных"""
        with self.db_manager.get_connection() as conn:
            for video in videos:
                # Генерируем ID видео если его нет
                video_id = video.get('video_id', f"{channel_id}_{hash(video['title'])}")
                
                # Парсим дату публикации
                published_at = video.get('published_at')
                if isinstance(published_at, str):
                    try:
                        published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    except:
                        published_at = datetime.now()
                
                # Сохраняем видео
                conn.execute("""
                    INSERT OR REPLACE INTO videos 
                    (video_id, channel_id, title, published_at, is_scheduled, 
                     scheduled_time, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (video_id, channel_id, video['title'], published_at,
                      video.get('is_scheduled', False), video.get('scheduled_time')))
                
                # Сохраняем статистику видео
                conn.execute("""
                    INSERT INTO video_stats 
                    (video_id, view_count, like_count, comment_count)
                    VALUES (?, ?, ?, ?)
                """, (video_id, video.get('views', 0), 
                      video.get('likes', 0), video.get('comments', 0)))
                
                # Сохраняем комментарии
                for comment in video.get('comment_list', []):
                    conn.execute("""
                        INSERT OR IGNORE INTO comments 
                        (video_id, author_name, comment_text, published_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """, (video_id, comment['author'], comment['text']))
            
            conn.commit()
    
    async def get_optimized_summary_stats(self) -> Dict:
        """Оптимизированная статистика с сохранением в БД"""
        result = await super().get_optimized_summary_stats()
        
        # Сохраняем агрегированные данные
        try:
            await self._save_summary_to_db(result)
        except Exception as e:
            logger.error(f"Error saving summary to DB: {e}")
        
        return result
    
    async def _save_summary_to_db(self, summary_data: Dict):
        """Сохраняет сводную статистику в БД"""
        today = datetime.now().date()
        
        # Сохраняем ежедневные агрегаты для каждого канала
        for channel in config.CHANNELS:
            channel_id = channel['channel_id']
            
            # Получаем статистику канала из сводки
            channel_today = next(
                (item for item in summary_data['detailed']['today'] 
                 if item['channel_name'] == channel['name']), 
                {'views': 0, 'likes': 0, 'comments': 0}
            )
            
            try:
                with self.db_manager.get_connection() as conn:
                    # Подсчитываем видео за сегодня
                    cursor = conn.execute("""
                        SELECT 
                            COUNT(*) as total_videos,
                            SUM(CASE WHEN is_scheduled = TRUE THEN 1 ELSE 0 END) as scheduled_videos
                        FROM videos 
                        WHERE channel_id = ? AND DATE(published_at) = ?
                    """, (channel_id, today))
                    
                    video_counts = cursor.fetchone()
                    videos_uploaded = (video_counts['total_videos'] or 0) - (video_counts['scheduled_videos'] or 0)
                    videos_scheduled = video_counts['scheduled_videos'] or 0
                    
                    # Сохраняем ежедневную статистику
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_channel_stats 
                        (channel_id, date, videos_uploaded, videos_scheduled, 
                         total_views, total_likes, total_comments)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (channel_id, today, videos_uploaded, videos_scheduled,
                          channel_today['views'], channel_today['likes'], 
                          channel_today['comments']))
                    
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Error saving daily stats for {channel_id}: {e}")
    
    def get_historical_trends(self, channel_id: str, days: int = 7) -> Dict[str, Any]:
        """Получает исторические тренды канала"""
        return self.historical.get_channel_trends(channel_id, days)
    
    def get_analytics_dashboard(self, days: int = 7) -> Dict[str, Any]:
        """Получает данные для аналитического дашборда"""
        try:
            # Базовая статистика
            summary = self.get_summary_stats()
            
            # Исторические тренды
            trends = {}
            for channel in config.CHANNELS:
                channel_id = channel['channel_id']
                trends[channel['name']] = self.historical.get_channel_trends(channel_id, days)
            
            # Топ контент
            top_content = self.historical.get_top_performing_content(days)
            
            # Аналитическая сводка
            analytics_summary = self.historical.get_analytics_summary(days)
            
            return {
                'summary': summary,
                'trends': trends,
                'top_content': top_content,
                'analytics': analytics_summary,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics dashboard: {e}")
            return {
                'summary': {'today': {'views': 0, 'likes': 0, 'comments': 0}},
                'trends': {},
                'top_content': {'top_videos': [], 'top_channels': []},
                'analytics': {},
                'error': str(e)
            }
    
    def calculate_daily_aggregates(self):
        """Вычисляет ежедневные агрегаты"""
        try:
            self.historical.calculate_daily_aggregates()
            logger.info("Daily aggregates calculated successfully")
        except Exception as e:
            logger.error(f"Error calculating daily aggregates: {e}")
    
    def calculate_trends(self, days_back: int = 7):
        """Вычисляет тренды"""
        try:
            self.historical.calculate_trends(days_back)
            logger.info(f"Trends calculated for {days_back} days")
        except Exception as e:
            logger.error(f"Error calculating trends: {e}")
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Очищает старые данные"""
        try:
            result = self.historical.cleanup_old_data(days_to_keep)
            self.cache.clear_expired()
            self.db_manager.vacuum_database()
            
            logger.info(f"Cleanup completed: {result}")
            return result
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {'error': str(e)}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Получает статистику базы данных"""
        try:
            db_stats = self.db_manager.get_database_stats()
            cache_stats = self.cache.get_stats()
            
            return {
                'database': db_stats,
                'cache': cache_stats,
                'status': 'healthy'
            }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {'error': str(e), 'status': 'error'}
    
    def export_data(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Экспортирует данные за период"""
        try:
            with self.db_manager.get_connection() as conn:
                # Экспорт ежедневной статистики
                cursor = conn.execute("""
                    SELECT 
                        c.channel_name,
                        dcs.date,
                        dcs.videos_uploaded,
                        dcs.videos_scheduled,
                        dcs.total_views,
                        dcs.total_likes,
                        dcs.total_comments,
                        dcs.subscriber_growth
                    FROM daily_channel_stats dcs
                    JOIN channels c ON dcs.channel_id = c.channel_id
                    WHERE dcs.date BETWEEN ? AND ?
                    ORDER BY dcs.date, c.channel_name
                """, (start_date.date(), end_date.date()))
                
                daily_stats = []
                for row in cursor.fetchall():
                    daily_stats.append(dict(row))
                
                # Экспорт трендов
                cursor = conn.execute("""
                    SELECT 
                        t.entity_type,
                        CASE 
                            WHEN t.entity_type = 'channel' THEN c.channel_name
                            ELSE t.entity_id
                        END as entity_name,
                        t.metric_name,
                        t.date,
                        t.current_value,
                        t.growth_absolute,
                        t.growth_percentage
                    FROM trends t
                    LEFT JOIN channels c ON t.entity_id = c.channel_id AND t.entity_type = 'channel'
                    WHERE t.date BETWEEN ? AND ?
                    ORDER BY t.date, t.entity_type, entity_name, t.metric_name
                """, (start_date.date(), end_date.date()))
                
                trends = []
                for row in cursor.fetchall():
                    trends.append(dict(row))
                
                return {
                    'daily_stats': daily_stats,
                    'trends': trends,
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    }
                }
                
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return {'error': str(e)}
    
    def migrate_from_json(self, json_file_path: str = "request_data.json"):
        """Мигрирует данные из JSON файлов в БД"""
        try:
            import json
            import os
            
            if not os.path.exists(json_file_path):
                logger.info(f"JSON file {json_file_path} not found, skipping migration")
                return
            
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self.db_manager.get_connection() as conn:
                # Мигрируем пользователей и их запросы
                for user_id_str, user_data in data.get('users', {}).items():
                    user_id = int(user_id_str)
                    
                    # Создаем пользователя
                    conn.execute("""
                        INSERT OR IGNORE INTO users (user_id) VALUES (?)
                    """, (user_id,))
                    
                    # Создаем запросы (примерные данные)
                    requests_today = user_data.get('requests_today', 0)
                    for i in range(requests_today):
                        conn.execute("""
                            INSERT INTO user_requests 
                            (user_id, request_type, timestamp)
                            VALUES (?, ?, ?)
                        """, (user_id, 'migrated_request', datetime.now()))
                
                # Мигрируем API квоту
                api_quota = data.get('api_quota', {})
                if api_quota:
                    today = datetime.now().date()
                    conn.execute("""
                        INSERT OR REPLACE INTO api_quota 
                        (date, quota_used, quota_limit)
                        VALUES (?, ?, ?)
                    """, (today, api_quota.get('used', 0), 10000))
                
                conn.commit()
                
            logger.info(f"Migration from {json_file_path} completed")
            
            # Переименовываем старый файл
            backup_name = f"{json_file_path}.backup"
            os.rename(json_file_path, backup_name)
            logger.info(f"Original file backed up as {backup_name}")
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
    
    # === Методы совместимости с ботом ===
    
    def get_summary_stats(self):
        """Совместимость с оригинальным API"""
        try:
            # Проверяем, запущен ли event loop
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже работает, используем синхронный подход
                logger.warning("Event loop already running, using synchronous approach for get_summary_stats")
                return self._get_summary_stats_sync()
            except RuntimeError:
                # Event loop не запущен, можем создать новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self.get_optimized_summary_stats())
                    return result.get('summary', self._get_default_summary())
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Error in get_summary_stats: {e}")
            return self._get_default_summary()
    
    def get_detailed_channel_stats(self):
        """Совместимость с оригинальным API"""
        try:
            # Проверяем, запущен ли event loop
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже работает, используем синхронный подход
                logger.warning("Event loop already running, using synchronous approach for get_detailed_channel_stats")
                return self._get_detailed_stats_sync()
            except RuntimeError:
                # Event loop не запущен, можем создать новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self.get_optimized_summary_stats())
                    return result.get('detailed', self._get_default_detailed())
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Error in get_detailed_channel_stats: {e}")
            return self._get_default_detailed()
    
    def get_daily_stats(self):
        """Получает статистику за день по всем каналам"""
        try:
            return self.get_stats_by_period(1)
        except Exception as e:
            logger.error(f"Error in get_daily_stats: {e}")
            return []
    
    def get_stats_by_period(self, days):
        """Получает статистику за указанный период по всем каналам"""
        try:
            return super().get_stats_by_period(days)
        except Exception as e:
            logger.error(f"Error in get_stats_by_period: {e}")
            return []
    
    def get_today_video_stats(self):
        """Получает статистику по видео за сегодня"""
        try:
            return super().get_today_video_stats()
        except Exception as e:
            logger.error(f"Error in get_today_video_stats: {e}")
            return {'uploaded': 0, 'scheduled': 0}
    
    def get_channel_stats(self, channel_id: str) -> Optional[Dict]:
        """Получает статистику одного канала (для совместимости)"""
        try:
            result = self.get_batch_channel_stats([channel_id])
            return result.get(channel_id)
        except Exception as e:
            logger.error(f"Error in get_channel_stats for {channel_id}: {e}")
            return None
    
    # === Вспомогательные синхронные методы ===
    
    def _get_default_summary(self):
        """Возвращает пустую структуру summary"""
        return {
            'today': {'views': 0, 'likes': 0, 'comments': 0},
            'yesterday': {'views': 0, 'likes': 0, 'comments': 0},
            'week': {'views': 0, 'likes': 0, 'comments': 0},
            'all_time': {'views': 0, 'likes': 0, 'comments': 0}
        }
    
    def _get_default_detailed(self):
        """Возвращает пустую структуру detailed"""
        return {
            'today': [],
            'yesterday': [],
            'week': []
        }
    
    def _get_summary_stats_sync(self):
        """Синхронное получение summary статистики"""
        try:
            # Получаем данные из кэша БД
            cache_key = "summary_stats_sync"
            cached_data = self._get_cached_data(cache_key, 'summary')
            if cached_data:
                return cached_data
                
            # Пытаемся получить данные через родительские синхронные методы
            try:
                today_stats = super().get_stats_by_period(1)  # Сегодня
                yesterday_stats = super().get_stats_by_period(2)  # Вчера  
                week_stats = super().get_stats_by_period(7)  # Неделя
                
                # Для "За все время" используем данные из БД
                all_time_stats = self._get_all_time_stats_from_db()
                
                # Агрегируем данные
                def aggregate_stats(stats_list):
                    total_views = sum(item.get('daily_views', 0) for item in stats_list)
                    total_likes = sum(item.get('daily_likes', 0) for item in stats_list)
                    total_comments = sum(item.get('daily_comments', 0) for item in stats_list)
                    return {'views': total_views, 'likes': total_likes, 'comments': total_comments}
                
                result = {
                    'today': aggregate_stats(today_stats),
                    'yesterday': aggregate_stats(yesterday_stats),
                    'week': aggregate_stats(week_stats),
                    'all_time': all_time_stats  # Используем данные из БД напрямую
                }
                
                # Кэшируем результат на 5 минут
                self._set_cached_data(cache_key, result, 'summary')
                return result
                
            except Exception as e:
                logger.warning(f"Failed to get summary stats via parent methods: {e}")
                # Если не получилось, возвращаем базовую структуру с данными из БД для all_time
                result = self._get_default_summary()
                try:
                    result['all_time'] = self._get_all_time_stats_from_db()
                except:
                    pass
                self._set_cached_data(cache_key, result, 'summary')
                return result
            
        except Exception as e:
            logger.error(f"Error in _get_summary_stats_sync: {e}")
            return self._get_default_summary()
    
    def _get_all_time_stats_from_db(self):
        """Получает статистику за все время из БД"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT 
                        COALESCE(SUM(vs.view_count), 0) as total_views,
                        COALESCE(SUM(vs.like_count), 0) as total_likes,
                        COALESCE(SUM(vs.comment_count), 0) as total_comments
                    FROM video_stats vs
                    JOIN videos v ON vs.video_id = v.video_id
                    JOIN channels c ON v.channel_id = c.channel_id
                ''')
                
                row = cursor.fetchone()
                return {
                    'views': int(row['total_views']),
                    'likes': int(row['total_likes']),
                    'comments': int(row['total_comments'])
                }
        except Exception as e:
            logger.error(f"Error getting all-time stats from DB: {e}")
            return {'views': 0, 'likes': 0, 'comments': 0}
    
    def _get_detailed_stats_sync(self):
        """Синхронное получение detailed статистики"""
        try:
            # Получаем данные из кэша БД
            cache_key = "detailed_stats_sync"
            cached_data = self._get_cached_data(cache_key, 'detailed')
            if cached_data:
                return cached_data
                
            # Пытаемся получить данные через родительские синхронные методы
            try:
                today_stats = super().get_stats_by_period(1)  # Сегодня
                yesterday_stats = super().get_stats_by_period(2)  # Вчера  
                week_stats = super().get_stats_by_period(7)  # Неделя
                
                result = {
                    'today': today_stats,
                    'yesterday': yesterday_stats,
                    'week': week_stats
                }
                
                # Кэшируем результат на 5 минут
                self._set_cached_data(cache_key, result, 'detailed')
                return result
                
            except Exception as e:
                logger.warning(f"Failed to get detailed stats via parent methods: {e}")
                # Если не получилось, возвращаем базовую структуру
                result = self._get_default_detailed()
                self._set_cached_data(cache_key, result, 'detailed')
                return result
            
        except Exception as e:
            logger.error(f"Error in _get_detailed_stats_sync: {e}")
            return self._get_default_detailed()
    
    def close(self):
        """Закрывает соединения с БД"""
        # Выполняем финальную очистку
        try:
            self.cache.clear_expired()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
