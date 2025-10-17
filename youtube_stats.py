from googleapiclient.discovery import build
from datetime import datetime, timedelta
import json
import os
import config
from channel_manager import channel_manager
import time
import logging
from typing import List

# Настройка логирования
logger = logging.getLogger(__name__)

class YouTubeStats:
    def __init__(self):
        try:
            self._api_keys: List[str] = [k for k in [config.YOUTUBE_API_KEY, getattr(config, 'YOUTUBE_API_KEY_2', None)] if k]
            self._api_key_index = 0
            self.youtube = build('youtube', 'v3', developerKey=self._api_keys[self._api_key_index])
            logger.info("YouTube API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize YouTube API client: {e}")
            raise
        self._cache = {}
        self._cache_timeout = 3600  # 1 час кэш для оптимизации
        # Файл для хранения базовых значений подписчиков по периодам
        self._subs_store_file = "subs_history.json"
        self._load_subs_store()

    def _rotate_api_key_and_rebuild(self) -> bool:
        """Переключает ключ на следующий и пересоздаёт клиент. Возвращает True, если ключ сменился."""
        if len(self._api_keys) <= 1:
            return False
        self._api_key_index = (self._api_key_index + 1) % len(self._api_keys)
        try:
            self.youtube = build('youtube', 'v3', developerKey=self._api_keys[self._api_key_index])
            logger.info("Rotated YouTube API key and rebuilt client")
            return True
        except Exception as e:
            logger.error(f"Failed to rebuild client with rotated key: {e}")
            return False

    def _is_quota_exceeded(self, error: Exception) -> bool:
        return 'quota' in str(error).lower() and 'exceed' in str(error).lower()
    
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
    
    def _resolve_channel_id_by_username(self, username: str) -> str:
        """Определяет channel_id по username/@handle через YouTube Data API v3.

        Приоритет:
        1) channels.list(forHandle='@handle')
        2) search.list(type='channel', q=handle)
        3) search.list(q='@handle')
        """
        if not username:
            return ""
        
        # Убираем @ если есть
        clean_username = username.lstrip('@')
        cache_key = f"channel_id_{clean_username}"
        
        # Проверяем кэш
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
        
        try:
            logger.info(f"Resolving channel_id for username: {clean_username}")
            handle_value = f"@{clean_username}"

            # Попытка 1: прямой lookup по handle
            try:
                direct_resp = self.youtube.channels().list(
                    part='id,snippet',
                    forHandle=handle_value
                ).execute()
                if direct_resp.get('items'):
                    channel_id = direct_resp['items'][0]['id']
                    logger.info(f"Found channel_id {channel_id} via forHandle for {handle_value}")
                    self._set_cached_data(cache_key, channel_id)
                    return channel_id
            except Exception as e:
                logger.info(f"forHandle lookup failed for {handle_value}: {e}")
                if self._is_quota_exceeded(e) and self._rotate_api_key_and_rebuild():
                    try:
                        direct_resp = self.youtube.channels().list(
                            part='id,snippet',
                            forHandle=handle_value
                        ).execute()
                        if direct_resp.get('items'):
                            channel_id = direct_resp['items'][0]['id']
                            self._set_cached_data(cache_key, channel_id)
                            return channel_id
                    except Exception:
                        pass
            
            # Метод 1: Прямой поиск по username
            search_response = self.youtube.search().list(
                part='snippet',
                type='channel',
                q=clean_username,
                maxResults=5  # Увеличиваем количество результатов
            ).execute()
            # При квоте попробуем второй ключ
            if not search_response and self._rotate_api_key_and_rebuild():
                try:
                    search_response = self.youtube.search().list(
                        part='snippet', type='channel', q=clean_username, maxResults=5
                    ).execute()
                except Exception:
                    search_response = None
            
            if search_response.get('items'):
                # Ищем точное совпадение по username
                for item in search_response['items']:
                    channel_snippet = item['snippet']
                    channel_title = channel_snippet.get('title', '').lower()
                    channel_custom_url = channel_snippet.get('customUrl', '').lower() if channel_snippet else ""
                    
                    # Проверяем точное совпадение username
                    if (clean_username.lower() in channel_title or 
                        clean_username.lower() == channel_custom_url or
                        f"@{clean_username.lower()}" == channel_custom_url):
                        channel_id = item['id']['channelId']
                        logger.info(f"Found channel_id {channel_id} for username {clean_username}")
                        self._set_cached_data(cache_key, channel_id)
                        return channel_id
                
                # Если точного совпадения нет, берем первый результат
                channel_id = search_response['items'][0]['id']['channelId']
                logger.info(f"Using first result channel_id {channel_id} for username {clean_username}")
                self._set_cached_data(cache_key, channel_id)
                return channel_id
            
            # Метод 2: Попробуем поиск по полному URL
            logger.info(f"Trying alternative search for username: {clean_username}")
            alt_search_response = self.youtube.search().list(
                part='snippet',
                type='channel',
                q=f"@{clean_username}",
                maxResults=3
            ).execute()
            if not alt_search_response and self._rotate_api_key_and_rebuild():
                try:
                    alt_search_response = self.youtube.search().list(
                        part='snippet', type='channel', q=f"@{clean_username}", maxResults=3
                    ).execute()
                except Exception:
                    alt_search_response = None
            
            if alt_search_response.get('items'):
                channel_id = alt_search_response['items'][0]['id']['channelId']
                logger.info(f"Found channel_id {channel_id} for @{clean_username}")
                self._set_cached_data(cache_key, channel_id)
                return channel_id
            
            logger.warning(f"No channel found for username: {clean_username}")
            return ""
                
        except Exception as e:
            logger.error(f"Error resolving channel_id for {clean_username}: {e}")
            return ""

    def _load_subs_store(self):
        """Загружает или инициализирует хранилище подписчиков"""
        try:
            if os.path.exists(self._subs_store_file):
                with open(self._subs_store_file, 'r', encoding='utf-8') as f:
                    self._subs_store = json.load(f)
            else:
                self._subs_store = {"channels": {}}
        except Exception as e:
            logger.warning(f"Failed to load subs store: {e}")
            self._subs_store = {"channels": {}}

    def _save_subs_store(self):
        """Сохраняет хранилище подписчиков"""
        try:
            with open(self._subs_store_file, 'w', encoding='utf-8') as f:
                json.dump(self._subs_store, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save subs store: {e}")

    def _get_period_keys(self):
        """Возвращает ключи периодов для сегодняшнего дня, вчера и недели"""
        now = datetime.utcnow()
        today_key = now.strftime('%Y-%m-%d')
        yesterday_key = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        week_key = f"week_{(now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')}"  # понедельник недели
        return today_key, yesterday_key, week_key

    def _update_and_get_subs_gains(self, channel_id: str, current_subs: int):
        """Обновляет базовые значения и возвращает прирост подписчиков по периодам (UTC).

        Логика:
        - baseline_today_subs — значение на начало текущего дня
        - baseline_week_subs — значение на начало текущей недели (понедельник 00:00 UTC)
        - снимок "вчера" сохраняется при смене дня как прежний baseline_today_subs
        """
        today_key, yesterday_key, week_key = self._get_period_keys()

        ch = self._subs_store.setdefault("channels", {}).setdefault(channel_id, {})

        # При смене дня переносим вчерашний срез до перезаписи baseline_today
        if ch.get("baseline_today_key") and ch.get("baseline_today_key") != today_key:
            prev_today_key = ch.get("baseline_today_key")
            prev_today_subs = int(ch.get("baseline_today_subs", current_subs))
            # Сохраняем baseline вчера, только если нет сохраненного
            if yesterday_key not in ch:
                ch[yesterday_key] = prev_today_subs

        # Инициализация/обновление baseline сегодня
        if ch.get("baseline_today_key") != today_key:
            ch["baseline_today_key"] = today_key
            ch["baseline_today_subs"] = int(current_subs)

        # Инициализация/обновление baseline недели
        if ch.get("baseline_week_key") != week_key:
            ch["baseline_week_key"] = week_key
            ch["baseline_week_subs"] = int(current_subs)

        # Вычисления прироста
        baseline_today = int(ch.get("baseline_today_subs", current_subs))
        baseline_week = int(ch.get("baseline_week_subs", current_subs))
        today_gain = max(0, int(current_subs) - baseline_today)
        week_gain = max(0, int(current_subs) - baseline_week)

        # Вчера = baseline сегодня - baseline вчера (если есть), иначе 0
        yesterday_baseline = ch.get(yesterday_key)
        if yesterday_baseline is None:
            yesterday_gain = 0
        else:
            yesterday_gain = max(0, baseline_today - int(yesterday_baseline))

        self._save_subs_store()

        return {
            'today': today_gain,
            'yesterday': yesterday_gain,
            'week': week_gain
        }
    
    def _chunk_list(self, items: List[str], chunk_size: int) -> List[List[str]]:
        """Разбивает список на чанки фиксированного размера"""
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    def get_channel_stats(self, channel_id, username=None):
        """Получает статистику канала с кэшированием"""
        # Если channel_id пуст, пытаемся определить по username
        if not channel_id and username:
            channel_id = self._resolve_channel_id_by_username(username)
            if not channel_id:
                logger.warning(f"Could not resolve channel_id for username: {username}")
                return None
        
        if not channel_id:
            logger.warning("No channel_id provided and no username to resolve")
            return None
            
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
            if self._is_quota_exceeded(e) and self._rotate_api_key_and_rebuild():
                try:
                    channel_response = self.youtube.channels().list(
                        part='statistics,snippet', id=channel_id
                    ).execute()
                    if channel_response.get('items'):
                        channel_info = channel_response['items'][0]
                        channel_name = channel_info['snippet']['title']
                        stats = channel_info['statistics']
                        result = {
                            'name': channel_name,
                            'subscribers': int(stats.get('subscriberCount', 0)),
                            'total_views': int(stats.get('viewCount', 0)),
                            'total_videos': int(stats.get('videoCount', 0))
                        }
                        self._set_cached_data(f"channel_stats_{channel_id}", result)
                        return result
                except Exception as e2:
                    logger.error(f"Retry after rotate failed: {e2}")
            return None
    
    def get_videos_for_period(self, channel_id, start_date, end_date, username=None):
        """Получает ВСЕ видео за период с пагинацией и кэшированием"""
        # Если channel_id пуст, пытаемся определить по username
        if not channel_id and username:
            channel_id = self._resolve_channel_id_by_username(username)
            if not channel_id:
                logger.warning(f"Could not resolve channel_id for username: {username}")
                return []
        
        if not channel_id:
            logger.warning("No channel_id provided and no username to resolve")
            return []
            
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
                # rotate on quota
                if not search_response and self._rotate_api_key_and_rebuild():
                    try:
                        search_response = self.youtube.search().list(
                            part='id,snippet', channelId=channel_id, order='date', type='video',
                            publishedAfter=start_date.isoformat() + 'Z',
                            publishedBefore=end_date.isoformat() + 'Z', maxResults=50, pageToken=next_page
                        ).execute()
                    except Exception:
                        search_response = {'items': []}

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
                    if not videos_info and self._rotate_api_key_and_rebuild():
                        try:
                            videos_info = self.youtube.videos().list(part='statistics,snippet', id=','.join(chunk)).execute()
                        except Exception:
                            videos_info = {'items': []}

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
    
    def get_recent_videos(self, channel_id, days=1, username=None):
        """Получает видео за последние N дней"""
        end_date = datetime.utcnow()
        
        if days == 1:  # Сегодня
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif days == 2:  # Вчера
            start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif days == 7:  # Неделя (с понедельника по воскресенье)
            current_weekday = end_date.weekday()  # 0=понедельник, 6=воскресенье
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=current_weekday)
        else:  # Все время
            start_date = datetime(2020, 1, 1)
        
        return self.get_videos_for_period(channel_id, start_date, end_date, username)
    
    def get_daily_stats(self):
        """Получает статистику за день по всем каналам (улучшенная версия)"""
        period_stats = []
        current_utc = datetime.utcnow()
        today_start = current_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        for channel in channel_manager.get_channels():
            try:
                channel_id = channel.get('channel_id', '')
                username = channel.get('username', '')
                
                # Если нет channel_id, пытаемся получить его по username
                if not channel_id and username:
                    channel_id = self._resolve_channel_id_by_username(username)
                
                if not channel_id:
                    continue
                
                channel_stats = self.get_channel_stats(channel_id, username)
                if not channel_stats:
                    continue

                today_end = today_start + timedelta(days=1)
                today_videos = self.get_videos_for_period(channel_id, today_start, today_end, username)

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
        
        for channel in channel_manager.get_channels():
            channel_id = channel.get('channel_id', '')
            username = channel.get('username', '')
            
            # Если нет channel_id, пытаемся получить его по username
            if not channel_id and username:
                channel_id = self._resolve_channel_id_by_username(username)
            
            if not channel_id:
                continue
            
            channel_stats = self.get_channel_stats(channel_id, username)
            if not channel_stats:
                continue
            
            videos = self.get_recent_videos(channel_id, days=days, username=username)
            
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
    
    def get_recent_channel_videos(self, channel_id, limit=50, username=None):
        """Получает последние видео канала для анализа статистики"""
        # Если channel_id пуст, пытаемся определить по username
        if not channel_id and username:
            channel_id = self._resolve_channel_id_by_username(username)
            if not channel_id:
                logger.warning(f"Could not resolve channel_id for username: {username}")
                return []
        
        if not channel_id:
            logger.warning("No channel_id provided and no username to resolve")
            return []
            
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
            
            # Неделя с понедельника по воскресенье
            current_weekday = current_utc.weekday()  # 0=понедельник, 6=воскресенье
            week_start = today_start - timedelta(days=current_weekday)
            
            for channel in channel_manager.get_channels():
                channel_id = channel.get('channel_id', '')
                channel_name = channel['name']
                username = channel.get('username', '')
                
                logger.info(f"Processing channel: {channel_name} (ID: {channel_id}, Username: {username})")
                
                # Если нет channel_id, пытаемся получить его по username
                if not channel_id and username:
                    try:
                        resolved_id = self._resolve_channel_id_by_username(username)
                        if resolved_id:
                            channel_id = resolved_id
                            logger.info(f"Resolved channel_id for {channel_name}: {channel_id}")
                        else:
                            logger.warning(f"Could not resolve channel_id for {channel_name} with username {username}")
                            continue
                    except Exception as e:
                        logger.error(f"Error resolving channel_id for {channel_name}: {e}")
                        continue
                
                if not channel_id:
                    logger.warning(f"No channel_id available for channel: {channel_name}")
                    continue
                
                channel_stats = self.get_channel_stats(channel_id, username)
                if not channel_stats:
                    logger.warning(f"Failed to get stats for channel: {channel_name}")
                    continue
                
                # Получаем видео по периодам через точные диапазоны
                today_end = today_start + timedelta(days=1)
                yesterday_end = today_start
                
                # Получаем видео за каждый период отдельно
                today_videos = self.get_videos_for_period(channel_id, today_start, today_end, channel.get('username'))
                yesterday_videos = self.get_videos_for_period(channel_id, yesterday_start, yesterday_end, channel.get('username'))
                week_videos = self.get_videos_for_period(channel_id, week_start, current_utc, channel.get('username'))
                
                all_channels_data[channel['name']] = {
                    'channel_stats': channel_stats,
                    'today_videos': today_videos,
                    'yesterday_videos': yesterday_videos,
                    'week_videos': week_videos
                }
                
                logger.info(f"Successfully processed channel: {channel_name} - Today: {len(today_videos)}, Yesterday: {len(yesterday_videos)}, Week: {len(week_videos)} videos")
            
            # Считаем сводную статистику
            summary = {
                'today': {'views': 0, 'likes': 0, 'comments': 0, 'subs_gain': 0, 'video_count': 0},
                'yesterday': {'views': 0, 'likes': 0, 'comments': 0, 'subs_gain': 0, 'video_count': 0},
                'week': {'views': 0, 'likes': 0, 'comments': 0, 'subs_gain': 0, 'video_count': 0},
                'all_time': {'views': 0, 'likes': 0, 'comments': 0, 'subscribers': 0, 'videos': 0}
            }
            
            for channel_name, data in all_channels_data.items():
                # Сегодня - ТОЛЬКО видео опубликованные сегодня и их текущая статистика
                for video in data['today_videos']:
                    summary['today']['views'] += video['views']
                    summary['today']['likes'] += video['likes']
                    summary['today']['comments'] += video['comments']
                logger.debug(f"Channel {channel_name} today contribution: {len(data['today_videos'])} videos")
                summary['today']['video_count'] += len(data['today_videos'])
                
                # Вчера - ТОЛЬКО видео опубликованные вчера и их текущая статистика
                for video in data['yesterday_videos']:
                    summary['yesterday']['views'] += video['views']
                    summary['yesterday']['likes'] += video['likes']
                    summary['yesterday']['comments'] += video['comments']
                summary['yesterday']['video_count'] += len(data['yesterday_videos'])
                
                # Неделя - все видео за неделю
                week_views_sum = 0
                week_likes_sum = 0
                week_comments_sum = 0
                for video in data['week_videos']:
                    week_views_sum += video['views']
                    week_likes_sum += video['likes']
                    week_comments_sum += video['comments']
                summary['week']['views'] += week_views_sum
                summary['week']['likes'] += week_likes_sum
                summary['week']['comments'] += week_comments_sum
                summary['week']['video_count'] += len(data['week_videos'])
                
                # Все время - используем общую статистику канала.
                # Если по какой-то причине общее число просмотров не получено (0/None),
                # используем безопасный фолбэк: недельную сумму, чтобы не было парадокса
                # "за неделю больше, чем за все время".
                channel_total_views = int(data['channel_stats'].get('total_views', 0) or 0)
                # Безопасность: не допускаем ситуации, когда all_time < week
                if channel_total_views < week_views_sum:
                    channel_total_views = week_views_sum
                summary['all_time']['views'] += channel_total_views
                # Для лайков и комментариев используем недельные данные как приближение
                summary['all_time']['likes'] += week_likes_sum
                summary['all_time']['comments'] += week_comments_sum
                summary['all_time']['subscribers'] += int(data['channel_stats'].get('subscribers', 0) or 0)
                summary['all_time']['videos'] += int(data['channel_stats'].get('total_videos', 0) or 0)

                # Прирост подписчиков
                channels = channel_manager.get_channels()
                channel_id = channels[[c['name'] for c in channels].index(channel_name)]['channel_id']
                gains = self._update_and_get_subs_gains(
                    channel_id=channel_id,
                    current_subs=int(data['channel_stats'].get('subscribers', 0) or 0)
                )
                summary['today']['subs_gain'] += gains['today']
                summary['yesterday']['subs_gain'] += gains['yesterday']
                summary['week']['subs_gain'] += gains['week']
            
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
            
            for channel in channel_manager.get_channels():
                channel_id = channel.get('channel_id', '')
                username = channel.get('username', '')
                
                # Если нет channel_id, пытаемся получить его по username
                if not channel_id and username:
                    channel_id = self._resolve_channel_id_by_username(username)
                
                if not channel_id:
                    continue
                
                # Получаем последние видео канала
                recent_videos = self.get_recent_channel_videos(channel_id, 50, username)
                
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
            
            for channel in channel_manager.get_channels():
                channel_id = channel.get('channel_id', '')
                channel_name = channel['name']
                channel_username = channel.get('username', '')
                
                # Если нет channel_id, пытаемся получить его по username
                if not channel_id and channel_username:
                    channel_id = self._resolve_channel_id_by_username(channel_username)
                
                if not channel_id:
                    # Добавляем канал с нулевой статистикой
                    detailed_stats['today'].append({
                        'channel_name': channel_name,
                        'channel_display': channel_name,
                        'views': 0,
                        'likes': 0,
                        'comments': 0
                    })
                    detailed_stats['yesterday'].append({
                        'channel_name': channel_name,
                        'channel_display': channel_name,
                        'views': 0,
                        'likes': 0,
                        'comments': 0
                    })
                    continue
                
                try:
                    # Получаем последние видео канала
                    recent_videos = self.get_recent_channel_videos(channel_id, 50, channel_username)
                    
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
        for channel in channel_manager.get_channels():
            channel_id = channel.get('channel_id', '')
            channel_name = channel['name']
            username = channel.get('username', '')
            
            # Если нет channel_id, пытаемся получить его по username
            if not channel_id and username:
                channel_id = self._resolve_channel_id_by_username(username)
            
            if not channel_id:
                issues.append(f"Канал {channel_name}: Нет channel_id и не удалось получить по username {username}")
                continue
            
            channel_ok, channel_message = self.test_channel_access(channel_id)
            if not channel_ok:
                issues.append(f"Канал {channel_name}: {channel_message}")
        
        return issues
