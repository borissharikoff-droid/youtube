import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class HistoricalDataManager:
    """Менеджер исторических данных и аналитики"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        logger.info("HistoricalDataManager initialized")
    
    def get_channel_trends(self, channel_id: str, days: int = 7) -> Dict[str, Any]:
        """Получает тренды канала за указанный период"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        metric_name,
                        date,
                        current_value,
                        growth_absolute,
                        growth_percentage
                    FROM trends 
                    WHERE entity_id = ? AND entity_type = 'channel'
                    AND date >= date('now', '-{} days')
                    ORDER BY metric_name, date
                """.format(days), (channel_id,))
                
                trends = {}
                for row in cursor.fetchall():
                    metric = row['metric_name']
                    if metric not in trends:
                        trends[metric] = []
                    
                    trends[metric].append({
                        'date': row['date'],
                        'value': row['current_value'],
                        'growth_absolute': row['growth_absolute'],
                        'growth_percentage': row['growth_percentage']
                    })
                
                return trends
        except Exception as e:
            logger.error(f"Error getting channel trends: {e}")
            return {}
    
    def get_top_performing_content(self, days: int = 7) -> Dict[str, Any]:
        """Получает топ контент за период"""
        try:
            with self.db.get_connection() as conn:
                # Топ видео по просмотрам
                cursor = conn.execute("""
                    SELECT 
                        v.title,
                        c.channel_name,
                        vs.view_count as views,
                        vs.like_count as likes,
                        vs.comment_count as comments
                    FROM video_stats vs
                    JOIN videos v ON vs.video_id = v.video_id
                    JOIN channels c ON v.channel_id = c.channel_id
                    WHERE vs.timestamp >= datetime('now', '-{} days')
                    ORDER BY vs.view_count DESC
                    LIMIT 10
                """.format(days))
                
                top_videos = []
                for row in cursor.fetchall():
                    top_videos.append(dict(row))
                
                # Топ каналы по активности
                cursor = conn.execute("""
                    SELECT 
                        c.channel_name,
                        COUNT(v.video_id) as video_count,
                        SUM(vs.view_count) as total_views,
                        SUM(vs.like_count) as total_likes
                    FROM channels c
                    LEFT JOIN videos v ON c.channel_id = v.channel_id
                    LEFT JOIN video_stats vs ON v.video_id = vs.video_id
                    WHERE vs.timestamp >= datetime('now', '-{} days')
                    GROUP BY c.channel_id, c.channel_name
                    ORDER BY total_views DESC
                    LIMIT 5
                """.format(days))
                
                top_channels = []
                for row in cursor.fetchall():
                    top_channels.append(dict(row))
                
                return {
                    'top_videos': top_videos,
                    'top_channels': top_channels
                }
        except Exception as e:
            logger.error(f"Error getting top content: {e}")
            return {'top_videos': [], 'top_channels': []}
    
    def get_analytics_summary(self, days: int = 7) -> Dict[str, Any]:
        """Получает аналитическую сводку"""
        try:
            with self.db.get_connection() as conn:
                # Общая статистика за период
                cursor = conn.execute("""
                    SELECT 
                        COUNT(DISTINCT c.channel_id) as active_channels,
                        COUNT(DISTINCT v.video_id) as total_videos_uploaded,
                        COALESCE(SUM(vs.view_count), 0) as total_views,
                        COALESCE(SUM(vs.like_count), 0) as total_likes,
                        COALESCE(SUM(vs.comment_count), 0) as total_comments
                    FROM channels c
                    LEFT JOIN videos v ON c.channel_id = v.channel_id
                    LEFT JOIN video_stats vs ON v.video_id = vs.video_id
                    WHERE vs.timestamp >= datetime('now', '-{} days')
                """.format(days))
                
                summary = dict(cursor.fetchone())
                
                # Рост подписчиков (примерная оценка)
                cursor = conn.execute("""
                    SELECT COALESCE(SUM(subscriber_growth), 0) as total_subscriber_growth
                    FROM daily_channel_stats
                    WHERE date >= date('now', '-{} days')
                """.format(days))
                
                growth_row = cursor.fetchone()
                summary['total_subscriber_growth'] = growth_row['total_subscriber_growth'] if growth_row else 0
                
                return summary
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}")
            return {}
    
    def calculate_daily_aggregates(self):
        """Вычисляет ежедневные агрегаты"""
        try:
            today = datetime.now().date()
            
            with self.db.get_connection() as conn:
                # Агрегируем данные по каждому каналу за сегодня
                cursor = conn.execute("""
                    SELECT DISTINCT channel_id FROM channels WHERE active = 1
                """)
                
                for row in cursor.fetchall():
                    channel_id = row['channel_id']
                    
                    # Подсчитываем статистику за сегодня
                    stats_cursor = conn.execute("""
                        SELECT 
                            COUNT(CASE WHEN v.is_scheduled = 0 THEN 1 END) as videos_uploaded,
                            COUNT(CASE WHEN v.is_scheduled = 1 THEN 1 END) as videos_scheduled,
                            COALESCE(SUM(vs.view_count), 0) as total_views,
                            COALESCE(SUM(vs.like_count), 0) as total_likes,
                            COALESCE(SUM(vs.comment_count), 0) as total_comments
                        FROM videos v
                        LEFT JOIN video_stats vs ON v.video_id = vs.video_id
                        WHERE v.channel_id = ? 
                        AND DATE(v.published_at) = ?
                        AND DATE(vs.timestamp) = ?
                    """, (channel_id, today, today))
                    
                    stats = stats_cursor.fetchone()
                    
                    # Сохраняем агрегат
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_channel_stats
                        (channel_id, date, videos_uploaded, videos_scheduled,
                         total_views, total_likes, total_comments)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (channel_id, today, 
                          stats['videos_uploaded'] or 0,
                          stats['videos_scheduled'] or 0,
                          stats['total_views'] or 0,
                          stats['total_likes'] or 0,
                          stats['total_comments'] or 0))
                
                conn.commit()
                logger.info("Daily aggregates calculated successfully")
                
        except Exception as e:
            logger.error(f"Error calculating daily aggregates: {e}")
    
    def calculate_trends(self, days_back: int = 7):
        """Вычисляет тренды роста"""
        try:
            with self.db.get_connection() as conn:
                # Получаем все каналы
                cursor = conn.execute("SELECT channel_id FROM channels WHERE active = 1")
                
                for row in cursor.fetchall():
                    channel_id = row['channel_id']
                    
                    # Вычисляем тренды для разных метрик
                    metrics = ['total_views', 'total_likes', 'total_comments']
                    
                    for metric in metrics:
                        # Получаем данные за последние дни
                        trend_cursor = conn.execute(f"""
                            SELECT date, {metric} as value
                            FROM daily_channel_stats
                            WHERE channel_id = ?
                            AND date >= date('now', '-{days_back} days')
                            ORDER BY date
                        """, (channel_id,))
                        
                        trend_data = trend_cursor.fetchall()
                        
                        # Вычисляем рост для каждого дня
                        for i, current_day in enumerate(trend_data):
                            if i > 0:  # Есть предыдущий день для сравнения
                                previous_day = trend_data[i-1]
                                current_value = current_day['value'] or 0
                                previous_value = previous_day['value'] or 0
                                
                                growth_absolute = current_value - previous_value
                                growth_percentage = (growth_absolute / previous_value * 100) if previous_value > 0 else 0
                                
                                # Сохраняем тренд
                                conn.execute("""
                                    INSERT OR REPLACE INTO trends
                                    (entity_type, entity_id, metric_name, date,
                                     current_value, previous_value, growth_absolute, growth_percentage)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, ('channel', channel_id, metric, current_day['date'],
                                      current_value, previous_value, growth_absolute, growth_percentage))
                
                conn.commit()
                logger.info(f"Trends calculated for {days_back} days")
                
        except Exception as e:
            logger.error(f"Error calculating trends: {e}")
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """Очищает старые данные"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with self.db.get_connection() as conn:
                # Очищаем старые записи
                tables_to_clean = [
                    ('video_stats', 'timestamp'),
                    ('channel_stats', 'timestamp'),
                    ('user_requests', 'timestamp'),
                    ('daily_channel_stats', 'date'),
                    ('trends', 'date'),
                    ('events', 'timestamp')
                ]
                
                cleaned = {}
                for table, date_column in tables_to_clean:
                    cursor = conn.execute(f"""
                        DELETE FROM {table} 
                        WHERE {date_column} < ?
                    """, (cutoff_date,))
                    
                    cleaned[table] = cursor.rowcount
                
                conn.commit()
                logger.info(f"Cleaned old data: {cleaned}")
                return cleaned
                
        except Exception as e:
            logger.error(f"Error cleaning old data: {e}")
            return {}