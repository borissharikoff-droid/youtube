from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
from database import DatabaseManager

logger = logging.getLogger(__name__)

class HistoricalDataManager:
    """Менеджер исторических данных и аналитики"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def store_channel_data(self, channel_id: str, channel_name: str, 
                          stats: Dict[str, Any], videos: List[Dict[str, Any]]):
        """Сохраняет данные канала и видео в БД"""
        with self.db.get_connection() as conn:
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
            
            # Сохраняем видео
            for video in videos:
                video_id = video.get('video_id') or f"{channel_id}_{video['title'][:50]}"
                
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
                    (video_id, channel_id, title, published_at, is_scheduled, scheduled_time, updated_at)
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
    
    def calculate_daily_aggregates(self, target_date: date = None):
        """Вычисляет ежедневные агрегаты для всех каналов"""
        if target_date is None:
            target_date = datetime.now().date()
        
        with self.db.get_connection() as conn:
            # Получаем все активные каналы
            cursor = conn.execute("SELECT channel_id FROM channels WHERE active = TRUE")
            channels = [row['channel_id'] for row in cursor.fetchall()]
            
            for channel_id in channels:
                self._calculate_channel_daily_stats(conn, channel_id, target_date)
            
            conn.commit()
    
    def _calculate_channel_daily_stats(self, conn, channel_id: str, target_date: date):
        """Вычисляет ежедневную статистику для канала"""
        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = date_start + timedelta(days=1)
        
        # Видео за день
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_videos,
                SUM(CASE WHEN is_scheduled = TRUE THEN 1 ELSE 0 END) as scheduled_videos
            FROM videos 
            WHERE channel_id = ? AND published_at BETWEEN ? AND ?
        """, (channel_id, date_start, date_end))
        
        video_stats = cursor.fetchone()
        videos_uploaded = video_stats['total_videos'] - video_stats['scheduled_videos']
        videos_scheduled = video_stats['scheduled_videos']
        
        # Статистика за день (берем последние значения)
        cursor = conn.execute("""
            SELECT 
                COALESCE(SUM(vs.view_count), 0) as total_views,
                COALESCE(SUM(vs.like_count), 0) as total_likes,
                COALESCE(SUM(vs.comment_count), 0) as total_comments
            FROM video_stats vs
            JOIN videos v ON vs.video_id = v.video_id
            WHERE v.channel_id = ? AND vs.timestamp BETWEEN ? AND ?
        """, (channel_id, date_start, date_end))
        
        stats = cursor.fetchone()
        
        # Рост подписчиков
        cursor = conn.execute("""
            SELECT 
                (SELECT subscriber_count FROM channel_stats 
                 WHERE channel_id = ? AND DATE(timestamp) = ?
                 ORDER BY timestamp DESC LIMIT 1) as current_subs,
                (SELECT subscriber_count FROM channel_stats 
                 WHERE channel_id = ? AND DATE(timestamp) = DATE(?, '-1 day')
                 ORDER BY timestamp DESC LIMIT 1) as previous_subs
        """, (channel_id, target_date, channel_id, target_date))
        
        subs_data = cursor.fetchone()
        current_subs = subs_data['current_subs'] or 0
        previous_subs = subs_data['previous_subs'] or 0
        subscriber_growth = current_subs - previous_subs
        
        # Сохраняем ежедневную статистику
        conn.execute("""
            INSERT OR REPLACE INTO daily_channel_stats 
            (channel_id, date, videos_uploaded, videos_scheduled, 
             total_views, total_likes, total_comments, subscriber_growth)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (channel_id, target_date, videos_uploaded, videos_scheduled,
              stats['total_views'], stats['total_likes'], 
              stats['total_comments'], subscriber_growth))
        
        # Записываем событие
        self._log_event(conn, 'daily_stats_calculated', 'channel', channel_id, 
                       description=f"Daily stats calculated for {target_date}")
    
    def calculate_trends(self, days_back: int = 7):
        """Вычисляет тренды для каналов и видео"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        with self.db.get_connection() as conn:
            # Тренды каналов
            self._calculate_channel_trends(conn, start_date, end_date)
            
            # Тренды видео
            self._calculate_video_trends(conn, start_date, end_date)
            
            conn.commit()
    
    def _calculate_channel_trends(self, conn, start_date: date, end_date: date):
        """Вычисляет тренды каналов"""
        cursor = conn.execute("""
            SELECT DISTINCT channel_id FROM daily_channel_stats 
            WHERE date BETWEEN ? AND ?
        """, (start_date, end_date))
        
        channels = [row['channel_id'] for row in cursor.fetchall()]
        
        for channel_id in channels:
            # Получаем данные за период
            cursor = conn.execute("""
                SELECT date, total_views, total_likes, total_comments, subscriber_growth
                FROM daily_channel_stats
                WHERE channel_id = ? AND date BETWEEN ? AND ?
                ORDER BY date
            """, (channel_id, start_date, end_date))
            
            daily_data = cursor.fetchall()
            if len(daily_data) < 2:
                continue
            
            # Вычисляем тренды для каждой метрики
            metrics = ['total_views', 'total_likes', 'total_comments']
            for metric in metrics:
                values = [row[metric] for row in daily_data]
                
                for i, current_value in enumerate(values[1:], 1):
                    previous_value = values[i-1]
                    growth_absolute = current_value - previous_value
                    growth_percentage = (growth_absolute / previous_value * 100) if previous_value > 0 else 0
                    
                    trend_date = daily_data[i]['date']
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO trends
                        (entity_type, entity_id, metric_name, date, 
                         current_value, previous_value, growth_absolute, growth_percentage)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, ('channel', channel_id, metric, trend_date,
                          current_value, previous_value, growth_absolute, growth_percentage))
    
    def _calculate_video_trends(self, conn, start_date: date, end_date: date):
        """Вычисляет тренды видео"""
        # Получаем видео с несколькими записями статистики
        cursor = conn.execute("""
            SELECT DISTINCT vs.video_id
            FROM video_stats vs
            JOIN videos v ON vs.video_id = v.video_id
            WHERE DATE(vs.timestamp) BETWEEN ? AND ?
            GROUP BY vs.video_id
            HAVING COUNT(*) > 1
        """, (start_date, end_date))
        
        video_ids = [row['video_id'] for row in cursor.fetchall()]
        
        for video_id in video_ids:
            cursor = conn.execute("""
                SELECT DATE(timestamp) as date, view_count, like_count, comment_count
                FROM video_stats
                WHERE video_id = ? AND DATE(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp
            """, (video_id, start_date, end_date))
            
            stats_data = cursor.fetchall()
            
            # Группируем по дням и берем последние значения
            daily_stats = {}
            for row in stats_data:
                daily_stats[row['date']] = {
                    'view_count': row['view_count'],
                    'like_count': row['like_count'],
                    'comment_count': row['comment_count']
                }
            
            # Вычисляем тренды
            dates = sorted(daily_stats.keys())
            metrics = ['view_count', 'like_count', 'comment_count']
            
            for metric in metrics:
                for i, current_date in enumerate(dates[1:], 1):
                    previous_date = dates[i-1]
                    
                    current_value = daily_stats[current_date][metric]
                    previous_value = daily_stats[previous_date][metric]
                    
                    growth_absolute = current_value - previous_value
                    growth_percentage = (growth_absolute / previous_value * 100) if previous_value > 0 else 0
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO trends
                        (entity_type, entity_id, metric_name, date,
                         current_value, previous_value, growth_absolute, growth_percentage)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, ('video', video_id, metric, current_date,
                          current_value, previous_value, growth_absolute, growth_percentage))
    
    def get_channel_trends(self, channel_id: str, days: int = 7) -> Dict[str, List[Dict]]:
        """Получает тренды канала за период"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT metric_name, date, current_value, growth_absolute, growth_percentage
                FROM trends
                WHERE entity_type = 'channel' AND entity_id = ? 
                AND date BETWEEN ? AND ?
                ORDER BY metric_name, date
            """, (channel_id, start_date, end_date))
            
            trends_data = cursor.fetchall()
            
            # Группируем по метрикам
            trends = {}
            for row in trends_data:
                metric = row['metric_name']
                if metric not in trends:
                    trends[metric] = []
                
                trends[metric].append({
                    'date': row['date'],
                    'value': row['current_value'],
                    'growth_absolute': row['growth_absolute'],
                    'growth_percentage': round(row['growth_percentage'], 2)
                })
            
            return trends
    
    def get_top_performing_content(self, days: int = 7, limit: int = 10) -> Dict[str, List[Dict]]:
        """Получает топ контент за период"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        with self.db.get_connection() as conn:
            # Топ видео по просмотрам
            cursor = conn.execute("""
                SELECT 
                    v.video_id, v.title, v.channel_id, c.channel_name,
                    MAX(vs.view_count) as max_views,
                    MAX(vs.like_count) as max_likes,
                    MAX(vs.comment_count) as max_comments
                FROM videos v
                JOIN channels c ON v.channel_id = c.channel_id
                JOIN video_stats vs ON v.video_id = vs.video_id
                WHERE vs.timestamp BETWEEN ? AND ?
                GROUP BY v.video_id
                ORDER BY max_views DESC
                LIMIT ?
            """, (start_date, end_date, limit))
            
            top_videos = []
            for row in cursor.fetchall():
                top_videos.append({
                    'video_id': row['video_id'],
                    'title': row['title'],
                    'channel_name': row['channel_name'],
                    'views': row['max_views'],
                    'likes': row['max_likes'],
                    'comments': row['max_comments']
                })
            
            # Топ каналы по росту
            cursor = conn.execute("""
                SELECT 
                    c.channel_id, c.channel_name,
                    SUM(dcs.total_views) as period_views,
                    SUM(dcs.total_likes) as period_likes,
                    SUM(dcs.subscriber_growth) as subscriber_growth
                FROM channels c
                JOIN daily_channel_stats dcs ON c.channel_id = dcs.channel_id
                WHERE dcs.date BETWEEN ? AND ?
                GROUP BY c.channel_id
                ORDER BY period_views DESC
                LIMIT ?
            """, (start_date.date(), end_date.date(), limit))
            
            top_channels = []
            for row in cursor.fetchall():
                top_channels.append({
                    'channel_id': row['channel_id'],
                    'channel_name': row['channel_name'],
                    'period_views': row['period_views'],
                    'period_likes': row['period_likes'],
                    'subscriber_growth': row['subscriber_growth']
                })
            
            return {
                'top_videos': top_videos,
                'top_channels': top_channels
            }
    
    def get_analytics_summary(self, days: int = 7) -> Dict[str, Any]:
        """Получает аналитическую сводку"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        with self.db.get_connection() as conn:
            # Общая статистика
            cursor = conn.execute("""
                SELECT 
                    COUNT(DISTINCT channel_id) as active_channels,
                    SUM(videos_uploaded) as total_videos_uploaded,
                    SUM(total_views) as total_views,
                    SUM(total_likes) as total_likes,
                    SUM(total_comments) as total_comments,
                    SUM(subscriber_growth) as total_subscriber_growth
                FROM daily_channel_stats
                WHERE date BETWEEN ? AND ?
            """, (start_date, end_date))
            
            summary = dict(cursor.fetchone())
            
            # Средние значения
            if summary['active_channels'] > 0:
                summary['avg_views_per_channel'] = summary['total_views'] // summary['active_channels']
                summary['avg_videos_per_channel'] = summary['total_videos_uploaded'] // summary['active_channels']
            
            # Лучший день
            cursor = conn.execute("""
                SELECT date, SUM(total_views) as day_views
                FROM daily_channel_stats
                WHERE date BETWEEN ? AND ?
                GROUP BY date
                ORDER BY day_views DESC
                LIMIT 1
            """, (start_date, end_date))
            
            best_day = cursor.fetchone()
            if best_day:
                summary['best_day'] = {
                    'date': best_day['date'],
                    'views': best_day['day_views']
                }
            
            return summary
    
    def _log_event(self, conn, event_type: str, entity_type: str = None, 
                   entity_id: str = None, user_id: int = None, 
                   description: str = None, metadata: Dict = None):
        """Записывает событие в лог"""
        metadata_json = json.dumps(metadata) if metadata else None
        
        conn.execute("""
            INSERT INTO events 
            (event_type, entity_type, entity_id, user_id, description, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event_type, entity_type, entity_id, user_id, description, metadata_json))
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Очищает старые данные"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with self.db.get_connection() as conn:
            # Очищаем старые события
            cursor = conn.execute("""
                DELETE FROM events WHERE timestamp < ?
            """, (cutoff_date,))
            events_deleted = cursor.rowcount
            
            # Очищаем старые запросы пользователей
            cursor = conn.execute("""
                DELETE FROM user_requests WHERE timestamp < ?
            """, (cutoff_date,))
            requests_deleted = cursor.rowcount
            
            # Очищаем старую статистику видео (оставляем по одной записи в день)
            conn.execute("""
                DELETE FROM video_stats 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM video_stats 
                    WHERE timestamp < ?
                    GROUP BY video_id, DATE(timestamp)
                ) AND timestamp < ?
            """, (cutoff_date, cutoff_date))
            
            conn.commit()
            
            self._log_event(conn, 'data_cleanup', description=f"Cleaned up data older than {days_to_keep} days")
            
            return {
                'events_deleted': events_deleted,
                'requests_deleted': requests_deleted
            }
