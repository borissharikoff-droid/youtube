import requests
from config import YOUTUBE_API_KEY

def find_channel_id(channel_name):
    """Поиск Channel ID по имени канала"""
    url = "https://www.googleapis.com/youtube/v3/search"
    
    params = {
        'part': 'snippet',
        'q': channel_name,
        'type': 'channel',
        'key': YOUTUBE_API_KEY,
        'maxResults': 5
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        print(f"🔍 Поиск канала: {channel_name}")
        print("=" * 50)
        
        if 'items' in data and data['items']:
            for i, item in enumerate(data['items'], 1):
                snippet = item['snippet']
                channel_id = item['id']['channelId']
                title = snippet['title']
                description = snippet['description'][:100] + "..." if len(snippet['description']) > 100 else snippet['description']
                
                print(f"{i}. {title}")
                print(f"   Channel ID: {channel_id}")
                print(f"   Описание: {description}")
                print(f"   URL: https://www.youtube.com/channel/{channel_id}")
                print("-" * 30)
        else:
            print("❌ Канал не найден")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при запросе: {e}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    # Поиск канала David Spitzer
    find_channel_id("David Spitzer")
    
    # Также можно поискать по username если знаем
    # find_channel_id("@davidspitzer")
