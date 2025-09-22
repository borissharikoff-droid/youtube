import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8208943672:AAGWCDFE7xNugXdsqilvnmojsY_pKMvW3wA")

# YouTube API Key
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyDBi9yLcdpYLR8jHG4FCG7Bq6mb7H1BWxs")

# Admin ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "250800600"))

# Настройки лимитов API
API_QUOTA_LIMIT = 10000  # Дневной лимит YouTube API (единиц)
API_QUOTA_PER_REQUEST = {
    'channels.list': 1,
    'videos.list': 1,
    'search.list': 100,
    'commentThreads.list': 1
}

# Лимиты запросов для пользователей
DAILY_REQUEST_LIMIT = 15  # Максимум запросов в день на пользователя
REQUEST_COOLDOWN = 120  # 2 минуты между запросами

# Список каналов для мониторинга
CHANNELS = [
    {
        "name": "Prime Fuel Nutrition",
        "channel_id": "UCpvd8ytFLL2E8Zgg6M0_itA",
        "username": "@primefuelnutrition"
    }
]

# ИСКЛЮЧЕННЫЕ КАНАЛЫ (пример формата):
# CHANNELS = [
#     {"name": "Example", "channel_id": "UCxxxxxxxxxxxxxxxxxx", "username": "@example"}
# ]
