import requests
from config import YOUTUBE_API_KEY, CHANNELS

def test_channel_data():
    """Тест получения данных канала"""
    print("🔍 Тестирую получение данных каналов...")
    print("=" * 60)
    
    for i, channel in enumerate(CHANNELS, 1):
        print(f"\n{i}. Канал: {channel['name']}")
        print(f"   Channel ID: {channel['channel_id']}")
        print(f"   Username: {channel['username']}")
        
        # Тест получения статистики канала
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'statistics,snippet',
            'id': channel['channel_id'],
            'key': YOUTUBE_API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            print(f"   📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if 'items' in data and data['items']:
                    stats = data['items'][0]['statistics']
                    snippet = data['items'][0]['snippet']
                    print(f"   ✅ Название: {snippet['title']}")
                    print(f"   👥 Подписчики: {stats.get('subscriberCount', 'N/A')}")
                    print(f"   👁️ Просмотры: {stats.get('viewCount', 'N/A')}")
                    print(f"   📹 Видео: {stats.get('videoCount', 'N/A')}")
                else:
                    print(f"   ❌ Канал не найден или недоступен")
            else:
                print(f"   ❌ Ошибка API: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        print("-" * 40)

def test_videos_search():
    """Тест поиска видео"""
    print("\n🔍 Тестирую поиск видео...")
    print("=" * 60)
    
    # Тестируем первый канал
    if CHANNELS:
        channel = CHANNELS[0]
        print(f"Канал: {channel['name']} ({channel['channel_id']})")
        
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'id,snippet',
            'channelId': channel['channel_id'],
            'order': 'date',
            'type': 'video',
            'maxResults': 5,
            'key': YOUTUBE_API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            print(f"📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"📝 Найдено видео: {len(data.get('items', []))}")
                
                for i, video in enumerate(data.get('items', []), 1):
                    title = video['snippet']['title']
                    published = video['snippet']['publishedAt']
                    print(f"   {i}. {title[:50]}... ({published})")
            else:
                print(f"❌ Ошибка: {response.text}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    print(f"🔑 API ключ: {YOUTUBE_API_KEY[:15]}...")
    test_channel_data()
    test_videos_search()
