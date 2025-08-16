import requests
from config import YOUTUBE_API_KEY

def test_api():
    """Тест YouTube API"""
    print(f"🔑 Используемый API ключ: {YOUTUBE_API_KEY[:10]}...")
    
    # Простой тест API
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': 'test',
        'type': 'video',
        'key': YOUTUBE_API_KEY,
        'maxResults': 1
    }
    
    try:
        print("🔄 Тестирую API...")
        response = requests.get(url, params=params)
        print(f"📊 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API работает!")
            print(f"📝 Найдено результатов: {data.get('pageInfo', {}).get('totalResults', 0)}")
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    test_api()
