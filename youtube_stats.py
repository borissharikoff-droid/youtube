from googleapiclient.discovery import build
from datetime import datetime, timedelta
import config
import time
import logging
from typing import List

# Настройка логирования
logger = logging.getLogger(__name__)

class YouTubeStats:
    def __init__(self):
        try:
            self.youtube = build('youtube', 'v3', developerKey=config.YOUTUBE_API_KEY)
            logger.info("YouTube API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize YouTube API client: {e}")
            raise
        self._cache = {}
        self._cache_timeout = 1800  # 30 минут кэш для оптимизации
    
    def _get_cached_data(self, key):
        """Получает данные из кэша"""
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < self._cache_timeout:
                return data
        return None
    
    def _set_cached_data(self, key, data):
        """Сохраняет данные в кэш"""
        self._cache[key] = (time.time(), data)
    
    def _chunk_list(self, items: List[str], chunk_size: int) -> List[List[str]]:
        """Разбивает список на чанки фиксированного размера"""
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    def get_channel_stats(self, channel_id):
        """Получает статистику канала с кэшированием"""
        cache_key = f"channel_stats_{channel_id}"
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
            
        try:
            logger.info(f"Fetching channel stats for {channel_id}")
            channel_response = self.youtube.channels().list(
                part='statistics,snippet',
                id=channel_id
            ).execute()
            
            if not channel_response.get('items'):
                logger.warning(f"No channel found for ID: {channel_id}")
                return None
            
            channel_info = channel_response['items'][0]
            channel_name = channel_info['snippet']['title']
            stats = channel_info['statistics']
            
            result = {
                'name': channel_name,
                'subscribers': int(stats.get('subscriberCount', 0)),
                'total_views': int(stats.get('viewCount', 0)),
                'total_videos': int(stats.get('videoCount', 0))
            }
            
            logger.info(f"Successfully fetched stats for channel: {channel_name}")
            self._set_cached_data(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Error fetching channel stats for {channel_id}: {e}")
            return None
    
    def get_videos_for_period(self, channel_id, start_date, end_date):
        """Получает ВСЕ видео за период с пагинацией и кэшированием"""
        cache_key = f"videos_{channel_id}_{start_date.date()}_{end_date.date()}"
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
            
        try:
            logger.info(f"Fetching videos for channel {channel_id} from {start_date} to {end_date}")

            videos = []
            next_page = None

            while True:
                search_response = self.youtube.search().list(
                    part='id,snippet',
                    channelId=channel_id,
                    order='date',
                    type='video',
                    publishedAfter=start_date.isoformat() + 'Z',
                    publishedBefore=end_date.isoformat() + 'Z',
                    maxResults=50,
                    pageToken=next_page
                ).execute()

                page_video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                if not page_video_ids:
                    if not next_page:
                        logger.info(f"No videos found for channel {channel_id} in the specified period")
                    break

                for chunk in self._chunk_list(page_video_ids, 50):
                    videos_info = self.youtube.videos().list(
                        part='statistics,snippet',
                        id=','.join(chunk)
                    ).execute()

                    for video in videos_info.get('items', []):
                        stats = video['statistics']
                        published_at = datetime.fromisoformat(
                            video['snippet']['publishedAt'].replace('Z', '+00:00')
                        )

                        is_scheduled = False
                        scheduled_time = None
                        if start_date.date() == datetime.utcnow().date():
                            current_utc = datetime.utcnow()
                            published_utc = published_at.replace(tzinfo=None)
                            is_scheduled = published_utc > current_utc
                            scheduled_time = published_at.strftime('%H:%M') if is_scheduled else None

                        video_comments = []
                        comment_count = int(stats.get('commentCount', 0))
                        if comment_count > 10:
                            try:
                                comments_response = self.youtube.commentThreads().list(
                                    part='snippet',
                                    videoId=video['id'],
                                    maxResults=2,
                                    order='relevance'
                                ).execute()
                                for comment in comments_response.get('items', []):
                                    comment_text = comment['snippet']['topLevelComment']['snippet']['textDisplay']
                                    author_name = comment['snippet']['topLevelComment']['snippet']['authorDisplayName']
                                    import re
                                    clean_text = re.sub(r'<[^>]+>', '', comment_text)
                                    video_comments.append({
                                        'author': author_name,
                                        'text': clean_text[:60] + "..." if len(clean_text) > 60 else clean_text
                                    })
                            except Exception as e:
                                logger.warning(f"Failed to fetch comments for video {video['id']}: {e}")
                                pass

                        videos.append({
                            'title': video['snippet']['title'],
                            'views': int(stats.get('viewCount', 0)),
                            'likes': int(stats.get('likeCount', 0)),
                            'comments': comment_count,
                            'published_at': video['snippet']['publishedAt'],
                            'published_datetime': published_at,
                            'is_scheduled': is_scheduled,
                            'scheduled_time': scheduled_time,
                            'comment_list': video_comments
                        })

                next_page = search_response.get('nextPageToken')
                if not next_page:
                    break

            logger.info(f"Successfully fetched {len(videos)} videos for channel {channel_id} in period")
            self._set_cached_data(cache_key, videos)
            return videos
        except Exception as e:
            logger.error(f"Error fetching videos for channel {channel_id}: {e}")
            return []
    
    def get_recent_videos(self, channel_id, days=1):
        """Получает видео за последние N дней"""
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
        
        return self.get_videos_for_period(channel_id, start_date, end_date)
    
    def get_daily_stats(self):
        """Получает статистику за день по всем каналам (улучшенная версия)"""
        period_stats = []
        current_utc = datetime.utcnow()
        today_start = current_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        for channel in config.CHANNELS:
            try:
                channel_stats = self.get_channel_stats(channel['channel_id'])
                if not channel_stats:
                    continue

                today_end = today_start + timedelta(days=1)
                today_videos = self.get_videos_for_period(channel['channel_id'], today_start, today_end)

                total_views = sum(v['views'] for v in today_videos)
                total_likes = sum(v['likes'] for v in today_videos)
                total_comments = sum(v['comments'] for v in today_videos)

                period_stats.append({
                    'channel_name': channel['name'],
                    'channel_username': channel.get('username', ''),
                    'channel_stats': channel_stats,
                    'videos': today_videos,
                    'daily_views': total_views,
                    'daily_likes': total_likes,
                    'daily_comments': total_comments
                })

            except Exception as e:
                logger.error(f"Error getting daily stats for channel {channel['name']}: {e}")
                continue
        
        return period_stats
    
    def get_stats_by_period(self, days):
        """Получает статистику за указанный период по всем каналам"""
        period_stats = []
        
        for channel in config.CHANNELS:
            channel_stats = self.get_channel_stats(channel['channel_id'])
            if not channel_stats:
                continue
            
            videos = self.get_recent_videos(channel['channel_id'], days=days)
            
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
    
    def get_recent_channel_videos(self, channel_id, limit=50):
        """Получает последние видео канала для анализа статистики"""
        cache_key = f"recent_videos_{channel_id}_{limit}"
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
            
        try:
            logger.info(f"Fetching recent videos for channel {channel_id}")
            
            # Получаем последние видео канала (без ограничения по дате)
            videos_response = self.youtube.search().list(
                part='id,snippet',
                channelId=channel_id,
                order='date',
                type='video',
                maxResults=limit
            ).execute()
            
            video_ids = [item['id']['videoId'] for item in videos_response['items']]
            
            if not video_ids:
                logger.info(f"No recent videos found for channel {channel_id}")
                self._set_cached_data(cache_key, [])
                return []
            
            # Получаем детальную информацию о видео
            videos_info = self.youtube.videos().list(
                part='statistics,snippet',
                id=','.join(video_ids)
            ).execute()
            
            videos = []
            for video in videos_info['items']:
                stats = video['statistics']
                published_at = datetime.fromisoformat(video['snippet']['publishedAt'].replace('Z', '+00:00'))
                
                videos.append({
                    'title': video['snippet']['title'],
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                    'published_at': video['snippet']['publishedAt'],
                    'published_datetime': published_at
                })
            
            logger.info(f"Successfully fetched {len(videos)} recent videos for channel {channel_id}")
            self._set_cached_data(cache_key, videos)
            return videos
        except Exception as e:
            logger.error(f"Error fetching recent videos for channel {channel_id}: {e}")
            return []

    def get_summary_stats_optimized(self):
        """
        Улучшенная версия получения сводной статистики
        
        ВАЖНО: Текущая логика показывает статистику видео, ОПУБЛИКОВАННЫХ в указанный период,
        а не прирост просмотров за этот период. Это означает:
        - "За сегодня" = статистика видео, опубликованных сегодня
        - "За вчера" = статистика видео, опубликованных вчера
        
        Для точного подсчета прироста просмотров нужно сравнивать снимки статистики
        каналов в разные дни, но это требует постоянного сохранения исторических данных.
        """
        try:
            logger.info("Starting to fetch summary stats for all channels")
            
            # Получаем все данные за один раз для каждого канала
            all_channels_data = {}
            current_utc = datetime.utcnow()
            
            # Определяем границы дней в UTC (можно улучшить для локальных зон)
            today_start = current_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today_start - timedelta(days=1)
            yesterday_end = today_start
            week_start = current_utc - timedelta(days=7)
            
            for channel in config.CHANNELS:
                channel_id = channel['channel_id']
                channel_name = channel['name']
                
                logger.info(f"Processing channel: {channel_name} ({channel_id})")
                
                channel_stats = self.get_channel_stats(channel_id)
                if not channel_stats:
                    logger.warning(f"Failed to get stats for channel: {channel_name}")
                    continue
                
                # Получаем видео за сегодня
                today_end = today_start + timedelta(days=1)
                recent_videos = self.get_videos_for_period(channel_id, today_start, today_end)
                # Получаем видео по периодам через точные диапазоны
                today_end = today_start + timedelta(days=1)
                recent_videos = self.get_videos_for_period(channel_id, today_start, today_end)
                
                # Фильтруем видео по периодам
                today_videos = []
                yesterday_videos = []
                week_videos = []
                
                for video in recent_videos:
                    pub_date = video['published_datetime'].replace(tzinfo=None)
                    
                    if pub_date >= today_start:
                        today_videos.append(video)
                    elif pub_date >= yesterday_start:
                        yesterday_videos.append(video)
                    
                    if pub_date >= week_start:
                        week_videos.append(video)
                
                all_channels_data[channel['name']] = {
                    'channel_stats': channel_stats,
                    'today_videos': today_videos,
                    'yesterday_videos': yesterday_videos,
                    'week_videos': week_videos
                }
                
                logger.info(f"Successfully processed channel: {channel_name} - Today: {len(today_videos)}, Yesterday: {len(yesterday_videos)}, Week: {len(week_videos)} videos")
            
            # Считаем сводную статистику
            summary = {
                'today': {'views': 0, 'likes': 0, 'comments': 0},
                'yesterday': {'views': 0, 'likes': 0, 'comments': 0},
                'week': {'views': 0, 'likes': 0, 'comments': 0},
                'all_time': {'views': 0, 'likes': 0, 'comments': 0}
            }
            
            for channel_name, data in all_channels_data.items():
                # Сегодня - ТОЛЬКО видео опубликованные сегодня и их текущая статистика
                for video in data['today_videos']:
                    summary['today']['views'] += video['views']
                    summary['today']['likes'] += video['likes']
                    summary['today']['comments'] += video['comments']
                logger.debug(f"Channel {channel_name} today contribution: {len(data['today_videos'])} videos")
                
                # Вчера - ТОЛЬКО видео опубликованные вчера и их текущая статистика
                for video in data['yesterday_videos']:
                    summary['yesterday']['views'] += video['views']
                    summary['yesterday']['likes'] += video['likes']
                    summary['yesterday']['comments'] += video['comments']
                
                # Неделя - все видео за неделю
                for video in data['week_videos']:
                    summary['week']['views'] += video['views']
                    summary['week']['likes'] += video['likes']
                    summary['week']['comments'] += video['comments']
                
                # Все время (общие просмотры канала)
                summary['all_time']['views'] += data['channel_stats']['total_views']
                # Для лайков и комментариев используем недельные данные как приближение
                summary['all_time']['likes'] += sum(v['likes'] for v in data['week_videos'])
                summary['all_time']['comments'] += sum(v['comments'] for v in data['week_videos'])
            
            logger.info("Successfully calculated summary stats")
            logger.info(f"Summary totals: Today {summary['today']}, Yesterday {summary['yesterday']}")
            logger.info(f"Week {summary['week']}, All-time {summary['all_time']}")
            
            # Дополнительная отладочная информация
            total_today_videos = sum(len(data['today_videos']) for data in all_channels_data.values())
            total_yesterday_videos = sum(len(data['yesterday_videos']) for data in all_channels_data.values())
            logger.info(f"Total videos processed: Today {total_today_videos}, Yesterday {total_yesterday_videos}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error in get_summary_stats_optimized: {e}")
            return {
                'today': {'views': 0, 'likes': 0, 'comments': 0},
                'yesterday': {'views': 0, 'likes': 0, 'comments': 0},
                'week': {'views': 0, 'likes': 0, 'comments': 0},
                'all_time': {'views': 0, 'likes': 0, 'comments': 0}
            }
    
    def get_summary_stats(self):
        """Получает сводную статистику по всем периодам (оптимизированная версия)"""
        return self.get_summary_stats_optimized()
    
    def get_today_video_stats(self):
        """Получает статистику по видео за сегодня (загруженные и в отложке) - улучшенная версия"""
        try:
            total_uploaded = 0
            total_scheduled = 0
            
            current_utc = datetime.utcnow()
            today_start = current_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            
            for channel in config.CHANNELS:
                channel_id = channel['channel_id']
                
                # Получаем последние видео канала
                recent_videos = self.get_recent_channel_videos(channel_id, 50)
                
                for video in recent_videos:
                    pub_date = video['published_datetime'].replace(tzinfo=None)
                    
                    # Проверяем, опубликовано ли видео сегодня
                    if pub_date >= today_start:
                        # Видео считается отложенным, если время публикации в будущем
                        if pub_date > current_utc:
                            total_scheduled += 1
                        else:
                            total_uploaded += 1
            
            logger.info(f"Today video stats: {total_uploaded} uploaded, {total_scheduled} scheduled")
            return {
                'uploaded': total_uploaded,
                'scheduled': total_scheduled,
                'total': total_uploaded + total_scheduled
            }
            
        except Exception as e:
            logger.error(f"Error in get_today_video_stats: {e}")
            return {'uploaded': 0, 'scheduled': 0, 'total': 0}

    def get_detailed_channel_stats(self):
        """Получает детальную статистику по каждому каналу за сегодня и вчера (улучшенная версия)"""
        try:
            detailed_stats = {
                'today': [],
                'yesterday': []
            }
            
            current_utc = datetime.utcnow()
            today_start = current_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today_start - timedelta(days=1)
            
            for channel in config.CHANNELS:
                channel_id = channel['channel_id']
                channel_name = channel['name']
                channel_username = channel.get('username', '')
                
                try:
                    # Получаем последние видео канала
                    recent_videos = self.get_recent_channel_videos(channel_id, 50)
                    
                    # Фильтруем и считаем статистику по периодам
                    today_views = today_likes = today_comments = 0
                    yesterday_views = yesterday_likes = yesterday_comments = 0
                    
                    for video in recent_videos:
                        pub_date = video['published_datetime'].replace(tzinfo=None)
                        
                        if pub_date >= today_start:
                            # Видео опубликовано сегодня
                            today_views += video['views']
                            today_likes += video['likes']
                            today_comments += video['comments']
                        elif yesterday_start <= pub_date < today_start:
                            # Видео опубликовано вчера
                            yesterday_views += video['views']
                            yesterday_likes += video['likes']
                            yesterday_comments += video['comments']
                    
                    logger.info(f"Channel {channel_name}: Today {today_views} views, Yesterday {yesterday_views} views")
                    
                except Exception as e:
                    logger.error(f"Error getting videos for channel {channel_name}: {e}")
                    # Устанавливаем нулевые значения при ошибке
                    today_views = today_likes = today_comments = 0
                    yesterday_views = yesterday_likes = yesterday_comments = 0
                
                # Формируем гиперссылку на канал
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    channel_display = f"[{channel_name}]({channel_link})"
                else:
                    channel_display = channel_name
                
                # Добавляем статистику за сегодня (всегда показываем канал)
                detailed_stats['today'].append({
                    'channel_name': channel_name,
                    'channel_display': channel_display,
                    'views': today_views,
                    'likes': today_likes,
                    'comments': today_comments
                })
                
                # Добавляем статистику за вчера (всегда показываем канал)
                detailed_stats['yesterday'].append({
                    'channel_name': channel_name,
                    'channel_display': channel_display,
                    'views': yesterday_views,
                    'likes': yesterday_likes,
                    'comments': yesterday_comments
                })
            
            return detailed_stats
            
        except Exception as e:
            logger.error(f"Error in get_detailed_channel_stats: {e}")
            return {'today': [], 'yesterday': []}

    def test_api_connection(self):
        """Тестирует подключение к YouTube API"""
        try:
            logger.info("Testing YouTube API connection...")
            
            # Пробуем получить информацию о популярных видео
            test_response = self.youtube.videos().list(
                part='snippet',
                chart='mostPopular',
                regionCode='US',
                maxResults=1
            ).execute()
            
            if test_response and 'items' in test_response:
                logger.info("YouTube API connection successful")
                return True, "API подключение работает"
            else:
                logger.error("YouTube API returned empty response")
                return False, "API вернул пустой ответ"
                
        except Exception as e:
            logger.error(f"YouTube API connection test failed: {e}")
            return False, f"Ошибка подключения к API: {str(e)}"
    
    def test_channel_access(self, channel_id):
        """Тестирует доступ к конкретному каналу"""
        try:
            logger.info(f"Testing access to channel: {channel_id}")
            
            channel_response = self.youtube.channels().list(
                part='snippet',
                id=channel_id
            ).execute()
            
            if channel_response['items']:
                channel_name = channel_response['items'][0]['snippet']['title']
                logger.info(f"Successfully accessed channel: {channel_name}")
                return True, f"Канал доступен: {channel_name}"
            else:
                logger.warning(f"Channel not found: {channel_id}")
                return False, "Канал не найден"
                
        except Exception as e:
            logger.error(f"Error testing channel access for {channel_id}: {e}")
            return False, f"Ошибка доступа к каналу: {str(e)}"
    
    def diagnose_issues(self):
        """Диагностирует возможные проблемы с API"""
        issues = []
        
        # Тестируем общее подключение к API
        api_ok, api_message = self.test_api_connection()
        if not api_ok:
            issues.append(f"API подключение: {api_message}")
        
        # Тестируем доступ к каждому каналу
        for channel in config.CHANNELS:
            channel_id = channel['channel_id']
            channel_name = channel['name']
            
            channel_ok, channel_message = self.test_channel_access(channel_id)
            if not channel_ok:
                issues.append(f"Канал {channel_name}: {channel_message}")
        
        return issues
