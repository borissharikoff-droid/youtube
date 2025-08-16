from googleapiclient.discovery import build
from datetime import datetime, timedelta
import config
import re
from collections import Counter
import time

class TrendsAnalyzer:
    def __init__(self):
        self.youtube = build('youtube', 'v3', developerKey=config.YOUTUBE_API_KEY)
        self._cache = {}
        self._cache_timeout = 1800  # 30 минут кэш для трендов
    
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
    
    def get_trending_videos(self, region_code='RU', category_id=None, max_results=50):
        """Получает трендовые видео"""
        cache_key = f"trending_{region_code}_{category_id}_{max_results}"
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
        
        try:
            # Получаем трендовые видео
            trending_response = self.youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=region_code,
                videoCategoryId=category_id,
                maxResults=max_results
            ).execute()
            
            videos = []
            for video in trending_response['items']:
                snippet = video['snippet']
                stats = video['statistics']
                
                # Извлекаем хештеги из описания
                description = snippet.get('description', '')
                hashtags = re.findall(r'#\w+', description)
                
                # Извлекаем теги
                tags = snippet.get('tags', [])
                
                videos.append({
                    'title': snippet['title'],
                    'description': description,
                    'video_id': video['id'],
                    'video_url': f"https://www.youtube.com/watch?v={video['id']}",
                    'category_id': snippet['categoryId'],
                    'category_name': self._get_category_name(snippet['categoryId']),
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                    'published_at': snippet['publishedAt'],
                    'hashtags': hashtags,
                    'tags': tags,
                    'channel_title': snippet['channelTitle'],
                    'duration': self._get_video_duration(video['id'])
                })
            
            self._set_cached_data(cache_key, videos)
            return videos
            
        except Exception as e:
            print(f"Ошибка при получении трендовых видео: {e}")
            return []
    
    def _get_category_name(self, category_id):
        """Получает название категории по ID"""
        categories = {
            '1': 'Фильмы и анимация',
            '2': 'Авто и транспорт',
            '10': 'Музыка',
            '15': 'Домашние животные и животные',
            '17': 'Спорт',
            '19': 'Путешествия и события',
            '20': 'Игры',
            '22': 'Люди и блоги',
            '23': 'Комедия',
            '24': 'Развлечения',
            '25': 'Новости и политика',
            '26': 'Как сделать и стиль',
            '27': 'Образование',
            '28': 'Наука и технологии',
            '29': 'Некоммерческие организации и активизм'
        }
        return categories.get(category_id, 'Другое')
    
    def _get_video_duration(self, video_id):
        """Получает длительность видео"""
        try:
            response = self.youtube.videos().list(
                part='contentDetails',
                id=video_id
            ).execute()
            
            if response['items']:
                duration = response['items'][0]['contentDetails']['duration']
                # Конвертируем ISO 8601 в минуты
                import re
                match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
                if match:
                    hours = int(match.group(1) or 0)
                    minutes = int(match.group(2) or 0)
                    seconds = int(match.group(3) or 0)
                    return hours * 60 + minutes + seconds / 60
            return 0
        except:
            return 0
    
    def analyze_trends(self, region_code='RU'):
        """Анализирует тренды и дает рекомендации"""
        try:
            # Получаем трендовые видео
            trending_videos = self.get_trending_videos(region_code=region_code, max_results=100)
            
            if not trending_videos:
                return None
            
            # Анализируем категории
            category_stats = {}
            for video in trending_videos:
                category = video['category_name']
                if category not in category_stats:
                    category_stats[category] = {
                        'count': 0,
                        'total_views': 0,
                        'total_likes': 0,
                        'videos': []
                    }
                
                category_stats[category]['count'] += 1
                category_stats[category]['total_views'] += video['views']
                category_stats[category]['total_likes'] += video['likes']
                category_stats[category]['videos'].append(video)
            
            # Анализируем хештеги
            all_hashtags = []
            for video in trending_videos:
                all_hashtags.extend(video['hashtags'])
            
            hashtag_freq = Counter(all_hashtags)
            top_hashtags = hashtag_freq.most_common(20)
            
            # Анализируем теги
            all_tags = []
            for video in trending_videos:
                all_tags.extend(video['tags'])
            
            tag_freq = Counter(all_tags)
            top_tags = tag_freq.most_common(20)
            
            # Анализируем длительность видео
            durations = [v['duration'] for v in trending_videos if v['duration'] > 0]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # Анализируем время публикации (переводим в MSK)
            publication_hours = []
            for video in trending_videos:
                published_at = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
                # Переводим в MSK (UTC+3)
                msk_time = published_at + timedelta(hours=3)
                publication_hours.append(msk_time.hour)
            
            hour_freq = Counter(publication_hours)
            best_hours = hour_freq.most_common(5)
            
            # Формируем рекомендации
            recommendations = self._generate_recommendations(
                category_stats, top_hashtags, top_tags, avg_duration, best_hours
            )
            
            # Фильтруем только виральные видео (с высоким количеством просмотров)
            viral_videos = [v for v in trending_videos if v['views'] > 100000]  # Минимум 100k просмотров
            if not viral_videos:
                viral_videos = trending_videos[:10]  # Если нет виральных, берем топ-10
            
            return {
                'trending_videos': viral_videos[:10],  # Топ-10 виральных видео
                'category_stats': category_stats,
                'top_hashtags': top_hashtags,
                'top_tags': top_tags,
                'avg_duration': avg_duration,
                'best_hours': best_hours,
                'recommendations': recommendations
            }
            
        except Exception as e:
            print(f"Ошибка при анализе трендов: {e}")
            return None
    
    def _generate_recommendations(self, category_stats, top_hashtags, top_tags, avg_duration, best_hours):
        """Генерирует рекомендации на основе анализа"""
        recommendations = {
            'top_categories': [],
            'video_ideas': [],
            'hashtag_suggestions': [],
            'timing_tips': [],
            'format_tips': []
        }
        
        # Топ категории
        sorted_categories = sorted(
            category_stats.items(), 
            key=lambda x: x[1]['total_views'], 
            reverse=True
        )
        recommendations['top_categories'] = sorted_categories[:5]
        
        # Идеи для видео на основе популярных категорий
        for category, stats in sorted_categories[:3]:
            if category == 'Развлечения':
                recommendations['video_ideas'].extend([
                    'Смешные моменты из жизни',
                    'Реакция на тренды',
                    'Челленджи и эксперименты'
                ])
            elif category == 'Люди и блоги':
                recommendations['video_ideas'].extend([
                    'День из жизни',
                    'Закулисные моменты',
                    'Вопросы и ответы'
                ])
            elif category == 'Музыка':
                recommendations['video_ideas'].extend([
                    'Каверы на популярные песни',
                    'Музыкальные моменты',
                    'Танцевальные видео'
                ])
        
        # Хештеги
        recommendations['hashtag_suggestions'] = [tag[0] for tag in top_hashtags[:10]]
        
        # Время публикации (MSK)
        recommendations['timing_tips'] = [
            f"Лучшее время: {hour}:00 МСК ({count} виральных видео)" 
            for hour, count in best_hours
        ]
        
        # Формат видео
        if avg_duration < 60:
            recommendations['format_tips'].append("Короткие видео (до 1 минуты) очень популярны")
        elif avg_duration < 300:
            recommendations['format_tips'].append("Средние видео (1-5 минут) показывают хорошие результаты")
        else:
            recommendations['format_tips'].append("Длинные видео (>5 минут) подходят для образовательного контента")
        
        return recommendations
    
    def get_personalized_recommendations(self, channel_name):
        """Получает персонализированные рекомендации для конкретного канала"""
        trends_data = self.analyze_trends()
        if not trends_data:
            return None
        
        # Анализируем канал и даем специфические рекомендации
        personalized = {
            'channel_name': channel_name,
            'trending_topics': trends_data['recommendations']['video_ideas'][:5],
            'hashtags': trends_data['recommendations']['hashtag_suggestions'][:10],
            'best_times': trends_data['recommendations']['timing_tips'][:3],
            'format_advice': trends_data['recommendations']['format_tips'],
            'trending_videos': trends_data['trending_videos'][:5]
        }
        
        return personalized
