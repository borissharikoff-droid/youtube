from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
import logging
from database import DatabaseManager, DatabaseRequestTracker

logger = logging.getLogger(__name__)

class DatabaseRequestTrackerExtended(DatabaseRequestTracker):
    """Request tracker на основе базы данных (расширенная версия)"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        if db_manager is None:
            db_manager = DatabaseManager()
        
        super().__init__(db_manager)
        self.db = db_manager
        
        # Мигрируем данные из JSON если есть
        self._migrate_from_json()
        
        logger.info("DatabaseRequestTracker initialized")
    
    def _migrate_from_json(self):
        """Мигрирует данные из старого JSON файла"""
        try:
            import json
            import os
            
            json_file = "request_data.json"
            if not os.path.exists(json_file):
                return
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self.db.get_connection() as conn:
                # Мигрируем пользователей
                for user_id_str, user_data in data.get('users', {}).items():
                    user_id = int(user_id_str)
                    
                    # Создаем пользователя
                    conn.execute("""
                        INSERT OR IGNORE INTO users (user_id) VALUES (?)
                    """, (user_id,))
                    
                    # Мигрируем запросы
                    requests_today = user_data.get('requests_today', 0)
                    last_request = user_data.get('last_request', 0)
                    
                    if last_request > 0:
                        last_request_time = datetime.fromtimestamp(last_request)
                        
                        # Создаем записи о запросах
                        for i in range(requests_today):
                            request_time = last_request_time - timedelta(hours=i)
                            conn.execute("""
                                INSERT INTO user_requests 
                                (user_id, request_type, timestamp, success)
                                VALUES (?, ?, ?, ?)
                            """, (user_id, 'migrated', request_time, True))
                
                # Мигрируем API квоту
                api_quota = data.get('api_quota', {})
                if api_quota:
                    today = datetime.now().date()
                    conn.execute("""
                        INSERT OR REPLACE INTO api_quota 
                        (date, quota_used, quota_limit)
                        VALUES (?, ?, ?)
                    """, (today, api_quota.get('used', 0), self.api_quota_limit))
                
                conn.commit()
            
            # Создаем бэкап старого файла
            backup_name = f"{json_file}.migrated.backup"
            os.rename(json_file, backup_name)
            logger.info(f"Migration completed, old file backed up as {backup_name}")
            
        except Exception as e:
            logger.error(f"Error during JSON migration: {e}")
    
    def get_user_activity_stats(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Получает расширенную статистику активности пользователя"""
        with self.db.get_connection() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Запросы по дням
            cursor = conn.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as requests,
                    SUM(api_quota_used) as quota_used,
                    AVG(response_time_ms) as avg_response_time,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errors
                FROM user_requests
                WHERE user_id = ? AND timestamp BETWEEN ? AND ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """, (user_id, start_date, end_date))
            
            daily_activity = []
            for row in cursor.fetchall():
                daily_activity.append({
                    'date': row['date'],
                    'requests': row['requests'],
                    'quota_used': row['quota_used'],
                    'avg_response_time': round(row['avg_response_time'] or 0, 2),
                    'errors': row['errors']
                })
            
            # Топ типов запросов
            cursor = conn.execute("""
                SELECT 
                    request_type,
                    COUNT(*) as count,
                    AVG(response_time_ms) as avg_response_time
                FROM user_requests
                WHERE user_id = ? AND timestamp BETWEEN ? AND ?
                GROUP BY request_type
                ORDER BY count DESC
            """, (user_id, start_date, end_date))
            
            request_types = []
            for row in cursor.fetchall():
                request_types.append({
                    'type': row['request_type'],
                    'count': row['count'],
                    'avg_response_time': round(row['avg_response_time'] or 0, 2)
                })
            
            # Общая статистика за период
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(api_quota_used) as total_quota,
                    AVG(response_time_ms) as avg_response_time,
                    MIN(timestamp) as first_request,
                    MAX(timestamp) as last_request,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as total_errors
                FROM user_requests
                WHERE user_id = ? AND timestamp BETWEEN ? AND ?
            """, (user_id, start_date, end_date))
            
            totals = dict(cursor.fetchone())
            
            return {
                'period_days': days,
                'daily_activity': daily_activity,
                'request_types': request_types,
                'totals': totals,
                'user_id': user_id
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Получает общую статистику системы"""
        with self.db.get_connection() as conn:
            today = datetime.now().date()
            
            # Статистика за сегодня
            cursor = conn.execute("""
                SELECT 
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(*) as total_requests,
                    SUM(api_quota_used) as quota_used,
                    AVG(response_time_ms) as avg_response_time,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errors
                FROM user_requests
                WHERE DATE(timestamp) = ?
            """, (today,))
            
            today_stats = dict(cursor.fetchone())
            
            # Топ активные пользователи
            cursor = conn.execute("""
                SELECT 
                    ur.user_id,
                    u.username,
                    COUNT(*) as requests,
                    SUM(ur.api_quota_used) as quota_used,
                    MAX(ur.timestamp) as last_activity
                FROM user_requests ur
                LEFT JOIN users u ON ur.user_id = u.user_id
                WHERE DATE(ur.timestamp) = ?
                GROUP BY ur.user_id
                ORDER BY requests DESC
                LIMIT 10
            """, (today,))
            
            top_users = []
            for row in cursor.fetchall():
                top_users.append({
                    'user_id': row['user_id'],
                    'username': row['username'],
                    'requests': row['requests'],
                    'quota_used': row['quota_used'],
                    'last_activity': row['last_activity']
                })
            
            # API квота
            cursor = conn.execute("""
                SELECT quota_used, quota_limit
                FROM api_quota
                WHERE date = ?
            """, (today,))
            
            quota_info = cursor.fetchone()
            api_quota = dict(quota_info) if quota_info else {
                'quota_used': 0, 
                'quota_limit': self.api_quota_limit
            }
            
            # Статистика ошибок
            cursor = conn.execute("""
                SELECT 
                    error_message,
                    COUNT(*) as count
                FROM user_requests
                WHERE DATE(timestamp) = ? AND success = FALSE
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT 5
            """, (today,))
            
            error_stats = []
            for row in cursor.fetchall():
                error_stats.append({
                    'error': row['error_message'],
                    'count': row['count']
                })
            
            return {
                'today': today_stats,
                'top_users': top_users,
                'api_quota': api_quota,
                'errors': error_stats,
                'date': today.isoformat()
            }
    
    def record_request_detailed(self, user_id: int, request_type: str, 
                              api_quota_used: int = 1, response_time_ms: int = None,
                              success: bool = True, error_message: str = None,
                              ip_address: str = None, metadata: Dict = None):
        """Расширенная запись запроса с дополнительными метаданными"""
        try:
            with self.db.get_connection() as conn:
                # Записываем запрос
                conn.execute("""
                    INSERT INTO user_requests 
                    (user_id, request_type, api_quota_used, response_time_ms, 
                     success, error_message, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, request_type, api_quota_used, response_time_ms, 
                      success, error_message, ip_address))
                
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
                    UPDATE users SET last_activity = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                """, (user_id,))
                
                # Записываем событие
                if metadata:
                    import json
                    conn.execute("""
                        INSERT INTO events 
                        (event_type, entity_type, entity_id, user_id, description, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, ('user_request', 'request', request_type, user_id,
                          f"User {user_id} made {request_type} request", 
                          json.dumps(metadata)))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error recording detailed request: {e}")
            # Fallback к обычной записи
            self.record_request(user_id, request_type, api_quota_used, 
                              response_time_ms, success, error_message)
    
    def get_quota_forecast(self, days_ahead: int = 1) -> Dict[str, Any]:
        """Прогнозирует использование квоты"""
        with self.db.get_connection() as conn:
            # Получаем историю использования квоты за последние 7 дней
            cursor = conn.execute("""
                SELECT date, quota_used
                FROM api_quota
                WHERE date >= DATE('now', '-7 days')
                ORDER BY date
            """)
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'date': row['date'],
                    'quota_used': row['quota_used']
                })
            
            if len(history) < 2:
                return {
                    'forecast': [],
                    'warning': 'Недостаточно данных для прогноза'
                }
            
            # Простой прогноз на основе среднего использования
            avg_daily_usage = sum(day['quota_used'] for day in history) / len(history)
            
            # Тренд (увеличивается или уменьшается использование)
            recent_avg = sum(day['quota_used'] for day in history[-3:]) / min(3, len(history))
            trend = recent_avg - avg_daily_usage
            
            forecast = []
            current_date = datetime.now().date()
            
            for i in range(1, days_ahead + 1):
                forecast_date = current_date + timedelta(days=i)
                predicted_usage = max(0, avg_daily_usage + (trend * i))
                
                forecast.append({
                    'date': forecast_date.isoformat(),
                    'predicted_usage': round(predicted_usage),
                    'quota_limit': self.api_quota_limit,
                    'utilization_percent': round((predicted_usage / self.api_quota_limit) * 100, 1)
                })
            
            return {
                'forecast': forecast,
                'historical_average': round(avg_daily_usage),
                'trend': 'increasing' if trend > 0 else 'decreasing' if trend < 0 else 'stable',
                'trend_value': round(trend, 2)
            }
    
    def cleanup_old_requests(self, days_to_keep: int = 30):
        """Очищает старые запросы"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM user_requests WHERE timestamp < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Cleaned up {deleted_count} old requests")
            return deleted_count
    
    def export_user_data(self, user_id: int, start_date: datetime = None, 
                        end_date: datetime = None) -> Dict[str, Any]:
        """Экспортирует данные пользователя"""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()
        
        with self.db.get_connection() as conn:
            # Основная информация о пользователе
            cursor = conn.execute("""
                SELECT * FROM users WHERE user_id = ?
            """, (user_id,))
            
            user_info = cursor.fetchone()
            if not user_info:
                return {'error': 'User not found'}
            
            # Запросы пользователя
            cursor = conn.execute("""
                SELECT * FROM user_requests
                WHERE user_id = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (user_id, start_date, end_date))
            
            requests = []
            for row in cursor.fetchall():
                requests.append(dict(row))
            
            return {
                'user_info': dict(user_info),
                'requests': requests,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_requests': len(requests)
            }
