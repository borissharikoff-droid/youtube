# YouTube Stats Telegram Bot

Telegram бот для мониторинга статистики YouTube каналов.

## Команды

- `/start` - Главное меню со сводной статистикой
- `/stats` - Детальная статистика за сегодня
- `/day` - Сводная статистика за день
- `/trends` - Анализ трендов YouTube
- `/help` - Справка

## Деплой на Railway

1. Загрузите код в GitHub
2. Подключите репозиторий к Railway
3. Установите переменные окружения:
   - `TELEGRAM_TOKEN` - токен вашего Telegram бота
   - `YOUTUBE_API_KEY` - ключ YouTube Data API v3
   - `ADMIN_ID` - ваш Telegram ID

## Отслеживаемые каналы

- @boom_shorts
- @SimpsonFanNumberOne  
- @BalkinFankouv
- @vidakapp

## Функции

- Мониторинг просмотров, лайков, комментариев
- Отслеживание отложенных видео
- Анализ трендов YouTube
- Интерактивные кнопки
- Кэширование для экономии API квоты
