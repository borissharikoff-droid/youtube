import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8208943672:AAGWCDFE7xNugXdsqilvnmojsY_pKMvW3wA")

# YouTube API Key
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyDBi9yLcdpYLR8jHG4FCG7Bq6mb7H1BWxs")

# Ваш Telegram ID
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

# Railway-specific settings
RAILWAY_MODE = os.getenv("RAILWAY_STATIC_URL") is not None
DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/youtube_tracker.db" if RAILWAY_MODE else "youtube_tracker.db")

# Обеспечиваем существование директории для БД в Railway
if RAILWAY_MODE:
    data_dir = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)

# Список каналов для мониторинга
CHANNELS = [
    {
        "name": "boom_shorts",
        "channel_id": "UCOzhymYx59BNUfv_sFcPjtA",
        "username": "@boom_shorts-s6u"
    },
    {
        "name": "Simpson Fan",
        "channel_id": "UCNwyOnZ1VfS-5lBd9_fXf5A",
        "username": "@simpsonfannumberone"
    },
    {
        "name": "Balkin Fankouv",
        "channel_id": "UC-mxDdjUpDpR8yZqYp6rOjw",
        "username": "@BalkinFankouv"
    },
    {
        "name": "VIDAK",
        "channel_id": "UCiJklQGS9xxChYyhmJZJXHQ",
        "username": "@vidakapp"
    },
    {
        "name": "David Spitzer",
        "channel_id": "UCpwsCGtcWd5ARq-SuGAqCcA",
        "username": "@DavidSpitzer-il9kx"
    },
    {
        "name": "NERSYANE",
        "channel_id": "UCVxRfn6OfDRk1ddym4KejWQ",
        "username": "@Ners1syane"
    },
    {
        "name": "Viral Mode_On",
        "channel_id": "UCn_H280ZWuIBRadhItgQ8nQ",
        "username": "@viralmode_1"
    }
    # Добавьте другие каналы по аналогии
]
