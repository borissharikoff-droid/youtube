import asyncio
import aiohttp
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os
# Выбираем конфигурацию в зависимости от среды
if os.getenv("RAILWAY_STATIC_URL"):
    import config_railway as config
else:
    import config
import time
import json
import os
from typing import List, Dict, Optional, Tuple

class OptimizedYouTubeStats:
    def __init__(self):
        self.youtube = build('youtube', 'v3', developerKey=config.YOUTUBE_API_KEY)
        self._cache = {}
        self._last_requests_file = "last_requests.json"
        
        # Разные TTL для разных типов данных
        self._cache_ttl = {
            'channel_stats': 3600,      # 1 час для статистики каналов
            'videos': 900,              # 15 минут для видео
            'comments': 1800,           # 30 минут для комментариев
            'search': 600               # 10 минут для поиска
        }
        
        # Загружаем информацию о последних запросах
        self._load_last_requests()
    
    def _load_last_requests(self):
        """Загружает информацию о последних запросах для инкрементальных обновлений"""
        try:
            if os.path.exists(self._last_requests_file):
                with open(self._last_requests_file, 'r', encoding='utf-8') as f:
                    self._last_requests = json.load(f)
            else:
                self._last_requests = {}
        except Exception as e:
            print(f"Ошибка загрузки последних запросов: {e}")
            self._last_requests = {}
    
    def _save_last_requests(self):
        """Сохраняет информацию о последних запросах"""
        try:
            with open(self._last_requests_file, 'w', encoding='utf-8') as f:
                json.dump(self._last_requests, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения последних запросов: {e}")
    
    def _get_cached_data(self, key: str, data_type: str = 'videos') -> Optional[Dict]:
        """Получает данные из кэша с учетом TTL для типа данных"""
        if key in self._cache:
            timestamp, data = self._cache[key]
            ttl = self._cache_ttl.get(data_type, 1800)
            if time.time() - timestamp < ttl:
                return data
        return None
    
    def _set_cached_data(self, key: str, data: Dict, data_type: str = 'videos'):
        """Сохраняет данные в кэш с типом данных"""
        self._cache[key] = (time.time(), data)
    
    def get_batch_channel_stats(self, channel_ids: List[str]) -> Dict[str, Dict]:
        """Получает статистику нескольких каналов за один запрос"""
        # Проверяем кэш для всех каналов
        results = {}
        uncached_ids = []
        
        for channel_id in channel_ids:
            cache_key = f"channel_stats_{channel_id}"
            cached = self._get_cached_data(cache_key, 'channel_stats')
            if cached:
                results[channel_id] = cached
            else:
                uncached_ids.append(channel_id)
        
        # Если есть некэшированные каналы, делаем batch запрос
        if uncached_ids:
            try:
                # Batch запрос для всех каналов сразу
                channel_response = self.youtube.channels().list(
                    part='statistics,snippet',
                    id=','.join(uncached_ids)  # Передаем все ID через запятую
                ).execute()
                
                for channel_info in channel_response.get('items', []):
                    channel_id = channel_info['id']
                    channel_name = channel_info['snippet']['title']
                    stats = channel_info['statistics']
                    
                    result = {
                        'name': channel_name,
                        'subscribers': int(stats.get('subscriberCount', 0)),
                        'total_views': int(stats.get('viewCount', 0)),
                        'total_videos': int(stats.get('videoCount', 0))
                    }
                    
                    # Кэшируем результат
                    cache_key = f"channel_stats_{channel_id}"
                    self._set_cached_data(cache_key, result, 'channel_stats')
                    results[channel_id] = result
                    
            except Exception as e:
                print(f"Ошибка получения статистики каналов: {e}")
                # Для неудачных запросов возвращаем None
                for channel_id in uncached_ids:
                    results[channel_id] = None
        
        return results
    
    def get_incremental_videos_for_period(self, channel_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Получает видео за период с инкрементальными обновлениями"""
        cache_key = f"videos_{channel_id}_{start_date.date()}_{end_date.date()}"
        cached = self._get_cached_data(cache_key, 'videos')
        
        # Для инкрементальных обновлений проверяем последний запрос
        last_request_key = f"last_video_request_{channel_id}"
        last_request_time = self._last_requests.get(last_request_key)
        
        # Если кэш свежий и недавно делали запрос, возвращаем кэш
        if cached and last_request_time:
            last_time = datetime.fromisoformat(last_request_time)
            if datetime.utcnow() - last_time < timedelta(minutes=15):
                return cached
        
        try:
            # Оптимизация: если это запрос за сегодня и у нас есть данные за сегодня,
            # ищем только видео новее последнего известного
            published_after = start_date
            if last_request_time and start_date.date() == datetime.utcnow().date():
                last_time = datetime.fromisoformat(last_request_time)
                published_after = max(start_date, last_time - timedelta(hours=1))  # Небольшой overlap
            
            # Получаем видео канала
            videos_response = self.youtube.search().list(
                part='id,snippet',
                channelId=channel_id,
                order='date',
                type='video',
                publishedAfter=published_after.isoformat() + 'Z',
                publishedBefore=end_date.isoformat() + 'Z',
                maxResults=50
            ).execute()
            
            video_ids = [item['id']['videoId'] for item in videos_response['items']]
            
            if not video_ids:
                # Если новых видео нет, но есть кэш, возвращаем кэш
                if cached:
                    return cached
                result = []
            else:
                # Получаем детальную информацию о видео (batch запрос)
                videos_info = self.youtube.videos().list(
                    part='statistics,snippet',
                    id=','.join(video_ids)  # Batch запрос для всех видео
                ).execute()
                
                result = []
                for video in videos_info['items']:
                    stats = video['statistics']
                    published_at = datetime.fromisoformat(video['snippet']['publishedAt'].replace('Z', '+00:00'))
                    
                    # Проверяем отложенные видео
                    is_scheduled = False
                    scheduled_time = None
                    if start_date.date() == datetime.utcnow().date():
                        current_utc = datetime.utcnow()
                        published_utc = published_at.replace(tzinfo=None)
                        is_scheduled = published_utc > current_utc
                        scheduled_time = published_at.strftime('%H:%M') if is_scheduled else None
                    
                    # Получаем комментарии только для популярных видео (оптимизация)
                    video_comments = []
                    comment_count = int(stats.get('commentCount', 0))
                    if comment_count > 50:  # Увеличили порог для экономии квоты
                        video_comments = self._get_video_comments(video['id'])
                    
                    result.append({
                        'title': video['snippet']['title'],
                        'views': int(stats.get('viewCount', 0)),
                        'likes': int(stats.get('likeCount', 0)),
                        'comments': comment_count,
                        'published_at': video['snippet']['publishedAt'],
                        'is_scheduled': is_scheduled,
                        'scheduled_time': scheduled_time,
                        'comment_list': video_comments
                    })
                
                # Если это инкрементальное обновление, объединяем с кэшем
                if cached and published_after > start_date:
                    # Фильтруем старые видео из кэша, чтобы избежать дубликатов
                    cached_videos = [v for v in cached if v['published_at'] < published_after.isoformat() + 'Z']
                    result = cached_videos + result
            
            # Обновляем время последнего запроса
            self._last_requests[last_request_key] = datetime.utcnow().isoformat()
            self._save_last_requests()
            
            # Кэшируем результат
            self._set_cached_data(cache_key, result, 'videos')
            return result
            
        except Exception as e:
            print(f"Ошибка получения видео для канала {channel_id}: {e}")
            # В случае ошибки возвращаем кэш, если есть
            return cached if cached else []
    
    def _get_video_comments(self, video_id: str) -> List[Dict]:
        """Получает комментарии к видео с кэшированием"""
        cache_key = f"comments_{video_id}"
        cached = self._get_cached_data(cache_key, 'comments')
        if cached:
            return cached
        
        try:
            comments_response = self.youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=3,  # Ограничиваем количество комментариев
                order='relevance'
            ).execute()
            
            video_comments = []
            for comment in comments_response.get('items', []):
                comment_text = comment['snippet']['topLevelComment']['snippet']['textDisplay']
                author_name = comment['snippet']['topLevelComment']['snippet']['authorDisplayName']
                # Очищаем HTML теги
                import re
                clean_text = re.sub(r'<[^>]+>', '', comment_text)
                video_comments.append({
                    'author': author_name,
                    'text': clean_text[:60] + "..." if len(clean_text) > 60 else clean_text
                })
            
            self._set_cached_data(cache_key, video_comments, 'comments')
            return video_comments
            
        except Exception as e:
            print(f"Ошибка получения комментариев для видео {video_id}: {e}")
            return []
    
    async def get_batch_videos_async(self, channel_periods: List[Tuple[str, datetime, datetime]]) -> Dict[str, List[Dict]]:
        """Асинхронно получает видео для нескольких каналов и периодов"""
        results = {}
        
        # Создаем задачи для параллельного выполнения
        async def get_videos_for_channel(channel_id: str, start_date: datetime, end_date: datetime):
            loop = asyncio.get_event_loop()
            # Выполняем синхронный код в thread pool
            return await loop.run_in_executor(
                None, 
                self.get_incremental_videos_for_period, 
                channel_id, start_date, end_date
            )
        
        # Запускаем все задачи параллельно
        tasks = []
        for channel_id, start_date, end_date in channel_periods:
            task = get_videos_for_channel(channel_id, start_date, end_date)
            tasks.append((channel_id, task))
        
        # Ждем завершения всех задач
        for channel_id, task in tasks:
            try:
                videos = await task
                results[channel_id] = videos
            except Exception as e:
                print(f"Ошибка получения видео для канала {channel_id}: {e}")
                results[channel_id] = []
        
        return results
    
    async def get_optimized_summary_stats(self) -> Dict:
        """Оптимизированная версия получения сводной статистики с async и батчингом"""
        try:
            # 1. Batch запрос статистики всех каналов
            channel_ids = [channel['channel_id'] for channel in config.CHANNELS]
            channels_stats = self.get_batch_channel_stats(channel_ids)
            
            # 2. Подготавливаем задачи для параллельного получения видео
            end_date = datetime.utcnow()
            
            # Определяем периоды
            today_start = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday_start + timedelta(days=1)
            week_start = end_date - timedelta(days=7)
            
            # Создаем список задач для всех каналов и периодов
            channel_periods = []
            for channel in config.CHANNELS:
                channel_id = channel['channel_id']
                channel_periods.extend([
                    (f"{channel_id}_today", channel_id, today_start, end_date),
                    (f"{channel_id}_yesterday", channel_id, yesterday_start, yesterday_end),
                    (f"{channel_id}_week", channel_id, week_start, end_date)
                ])
            
            # 3. Параллельно получаем все видео
            video_tasks = []
            for task_id, channel_id, start_date, end_date in channel_periods:
                video_tasks.append((task_id, channel_id, start_date, end_date))
            
            # Выполняем все запросы видео параллельно
            all_videos = await self.get_batch_videos_async([(c, s, e) for _, c, s, e in video_tasks])
            
            # 4. Агрегируем результаты
            summary = {
                'today': {'views': 0, 'likes': 0, 'comments': 0},
                'yesterday': {'views': 0, 'likes': 0, 'comments': 0},
                'week': {'views': 0, 'likes': 0, 'comments': 0},
                'all_time': {'views': 0, 'likes': 0, 'comments': 0}
            }
            
            detailed_stats = {'today': [], 'yesterday': []}
            
            for channel in config.CHANNELS:
                channel_id = channel['channel_id']
                channel_name = channel['name']
                channel_username = channel.get('username', '')
                
                # Получаем видео для каждого периода
                today_videos = all_videos.get(channel_id, [])
                yesterday_key = f"{channel_id}_yesterday"  # Нужно исправить логику получения видео за вчера
                week_key = f"{channel_id}_week"
                
                # Временное решение - используем те же видео (нужно доработать)
                today_videos_filtered = [v for v in today_videos 
                                       if datetime.fromisoformat(v['published_at'].replace('Z', '+00:00')).date() == today_start.date()]
                yesterday_videos_filtered = [v for v in today_videos 
                                           if datetime.fromisoformat(v['published_at'].replace('Z', '+00:00')).date() == yesterday_start.date()]
                week_videos = today_videos  # Упрощение для демо
                
                # Агрегируем статистику
                today_stats = self._aggregate_video_stats(today_videos_filtered)
                yesterday_stats = self._aggregate_video_stats(yesterday_videos_filtered)
                week_stats = self._aggregate_video_stats(week_videos)
                
                # Обновляем сводную статистику
                summary['today']['views'] += today_stats['views']
                summary['today']['likes'] += today_stats['likes']
                summary['today']['comments'] += today_stats['comments']
                
                summary['yesterday']['views'] += yesterday_stats['views']
                summary['yesterday']['likes'] += yesterday_stats['likes']
                summary['yesterday']['comments'] += yesterday_stats['comments']
                
                summary['week']['views'] += week_stats['views']
                summary['week']['likes'] += week_stats['likes']
                summary['week']['comments'] += week_stats['comments']
                
                # All time views из статистики канала
                channel_stat = channels_stats.get(channel_id)
                if channel_stat:
                    summary['all_time']['views'] += channel_stat['total_views']
                    # Для лайков и комментариев используем недельные данные
                    summary['all_time']['likes'] += week_stats['likes']
                    summary['all_time']['comments'] += week_stats['comments']
                
                # Детальная статистика по каналам
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    channel_display = f"[{channel_name}]({channel_link})"
                else:
                    channel_display = channel_name
                
                detailed_stats['today'].append({
                    'channel_name': channel_name,
                    'channel_display': channel_display,
                    'views': today_stats['views'],
                    'likes': today_stats['likes'],
                    'comments': today_stats['comments']
                })
                
                detailed_stats['yesterday'].append({
                    'channel_name': channel_name,
                    'channel_display': channel_display,
                    'views': yesterday_stats['views'],
                    'likes': yesterday_stats['likes'],
                    'comments': yesterday_stats['comments']
                })
            
            return {
                'summary': summary,
                'detailed': detailed_stats
            }
            
        except Exception as e:
            print(f"Ошибка получения оптимизированной статистики: {e}")
            return {
                'summary': {
                    'today': {'views': 0, 'likes': 0, 'comments': 0},
                    'yesterday': {'views': 0, 'likes': 0, 'comments': 0},
                    'week': {'views': 0, 'likes': 0, 'comments': 0},
                    'all_time': {'views': 0, 'likes': 0, 'comments': 0}
                },
                'detailed': {'today': [], 'yesterday': []}
            }
    
    def _aggregate_video_stats(self, videos: List[Dict]) -> Dict[str, int]:
        """Агрегирует статистику видео"""
        return {
            'views': sum(video['views'] for video in videos),
            'likes': sum(video['likes'] for video in videos),
            'comments': sum(video['comments'] for video in videos)
        }
    
    # Методы совместимости с оригинальным классом
    def get_summary_stats(self):
        """Совместимость с оригинальным API"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.get_optimized_summary_stats())
            return result['summary']
        finally:
            loop.close()
    
    def get_detailed_channel_stats(self):
        """Совместимость с оригинальным API"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.get_optimized_summary_stats())
            return result['detailed']
        finally:
            loop.close()
    
    def get_daily_stats(self):
        """Получает статистику за день по всем каналам"""
        return self.get_stats_by_period(1)
    
    def get_stats_by_period(self, days):
        """Получает статистику за указанный период по всем каналам"""
        period_stats = []
        
        end_date = datetime.utcnow()
        if days == 1:  # Сегодня
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif days == 2:  # Вчера
            start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif days == 7:  # Неделя
            start_date = end_date - timedelta(days=7)
        else:  # Все время
            start_date = datetime(2020, 1, 1)
        
        # Получаем статистику каналов batch запросом
        channel_ids = [channel['channel_id'] for channel in config.CHANNELS]
        channels_stats = self.get_batch_channel_stats(channel_ids)
        
        for channel in config.CHANNELS:
            channel_id = channel['channel_id']
            channel_stats = channels_stats.get(channel_id)
            if not channel_stats:
                continue
            
            videos = self.get_incremental_videos_for_period(channel_id, start_date, end_date)
            
            # Считаем общую статистику за период
            total_views = sum(video['views'] for video in videos)
            total_likes = sum(video['likes'] for video in videos)
            total_comments = sum(video['comments'] for video in videos)
            
            period_stats.append({
                'channel_name': channel['name'],
                'channel_username': channel.get('username', ''),
                'channel_stats': channel_stats,
                'videos': videos,
                'daily_views': total_views,
                'daily_likes': total_likes,
                'daily_comments': total_comments
            })
        
        return period_stats
    
    def get_today_video_stats(self):
        """Получает статистику по видео за сегодня (загруженные и в отложке)"""
        try:
            total_uploaded = 0
            total_scheduled = 0
            
            current_utc = datetime.utcnow()
            today_start = current_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = current_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Используем batch запрос для всех каналов
            for channel in config.CHANNELS:
                channel_id = channel['channel_id']
                videos = self.get_incremental_videos_for_period(channel_id, today_start, today_end)
                
                for video in videos:
                    published_at = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
                    published_utc = published_at.replace(tzinfo=None)
                    
                    if published_utc > current_utc:
                        total_scheduled += 1
                    else:
                        total_uploaded += 1
            
            return {
                'uploaded': total_uploaded,
                'scheduled': total_scheduled,
                'total': total_uploaded + total_scheduled
            }
            
        except Exception as e:
            print(f"Ошибка получения статистики видео за сегодня: {e}")
            return {'uploaded': 0, 'scheduled': 0, 'total': 0}
