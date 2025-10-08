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

# YouTube API Keys
YOUTUBE_API_KEY = _require_env("YOUTUBE_API_KEY")
# Optional second key for rotation
YOUTUBE_API_KEY_2 = os.getenv("YOUTUBE_API_KEY_2")

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

# Лимиты запросов для пользователей (сохраняем текущие значения)
DAILY_REQUEST_LIMIT = 15  # Максимум запросов в день на пользователя
REQUEST_COOLDOWN = 120  # 2 минуты между запросами

# Путь к базе данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "youtube_tracker.db")

# Список каналов для мониторинга
CHANNELS = [
    {
        "name": "TrueBeasts Journal (lumari)",
        "channel_id": "UChxGGarAwE9lWlnoNKnmoUw",
        "username": "@LongQuachThuy-b9l8b"
    },
    {
        "name": "Human Thread Story (cutli)",
        "channel_id": "UCwSQVMelX48iJmYsUwXSEpg",
        "username": "@HaDangMinh-t7j9g"
    }
]

# Обновлено: 2025-01-27 - переименованы каналы и удалены Prime Fuel Nutrition и vanessalibran

# ИСКЛЮЧЕННЫЕ КАНАЛЫ (пример формата):
# CHANNELS = [
#     {"name": "Example", "channel_id": "UCxxxxxxxxxxxxxxxxxx", "username": "@example"}
# ]
