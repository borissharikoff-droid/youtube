import os
from dotenv import load_dotenv

load_dotenv()

def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Environment variable {var_name} is required but not set")
    return value

# Telegram Bot Token (required)
TELEGRAM_TOKEN = _require_env("TELEGRAM_TOKEN")

# YouTube API Key (required)
YOUTUBE_API_KEY = _require_env("YOUTUBE_API_KEY")

# Admin ID (required)
ADMIN_ID = int(_require_env("ADMIN_ID"))

# Настройки лимитов API
API_QUOTA_LIMIT = 10000  # Дневной лимит YouTube API (единиц)
API_QUOTA_PER_REQUEST = {
    'channels.list': 1,
    'videos.list': 1,
    'search.list': 100,
    'commentThreads.list': 1
}

# Лимиты запросов для пользователей
DAILY_REQUEST_LIMIT = 100  # Максимум запросов в день на пользователя
REQUEST_COOLDOWN = 10  # 10 секунд между запросами

# Список каналов для мониторинга
CHANNELS = [
    {
        "name": "Prime Fuel Nutrition",
        "channel_id": "UCpvd8ytFLL2E8Zgg6M0_itA",
        "username": "@primefuelnutrition"
    }
]

# Обновлено: 2025-01-27 - добавлен канал Prime Fuel Nutrition

# ИСКЛЮЧЕННЫЕ КАНАЛЫ (пример формата):
# CHANNELS = [
#     {"name": "Example", "channel_id": "UCxxxxxxxxxxxxxxxxxx", "username": "@example"}
# ]
