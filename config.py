import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8208943672:AAGWCDFE7xNugXdsqilvnmojsY_pKMvW3wA")

# YouTube API Key
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyDBi9yLcdpYLR8jHG4FCG7Bq6mb7H1BWxs")

# Ваш Telegram ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "250800600"))

# Список каналов для мониторинга
CHANNELS = [
    {
        "name": "boom_shorts",
        "channel_id": "UCOzhymYx59BNUfv_sFcPjtA",
        "username": "@boom_shorts"
    },
    {
        "name": "Simpson Fan",
        "channel_id": "UCNwyOnZ1VfS-5lBd9_fXf5A",
        "username": "@SimpsonFanNumberOne"
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
    }
    # Добавьте другие каналы по аналогии
]
