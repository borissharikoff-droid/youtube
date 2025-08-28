import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import config
from youtube_stats import YouTubeStats
from request_tracker import RequestTracker

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверяем конфигурацию при запуске
try:
    logger.info("Starting YouTube Stats Bot (Simple Version)...")
    logger.info(f"Telegram Token: {'Set' if config.TELEGRAM_TOKEN else 'Not set'}")
    logger.info(f"YouTube API Key: {'Set' if config.YOUTUBE_API_KEY else 'Not set'}")
    logger.info(f"Admin ID: {config.ADMIN_ID}")
    logger.info(f"Channels to monitor: {len(config.CHANNELS)}")
except Exception as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)

def get_error_message(e):
    """Возвращает понятное сообщение об ошибке"""
    error_message = "Произошла ошибка при получении статистики."
    error_str = str(e).lower()
    
    if "quotaexceeded" in error_str or "quota exceeded" in error_str:
        error_message = "Превышен лимит запросов к YouTube API. Попробуйте позже."
    elif "accessnotconfigured" in error_str or "access not configured" in error_str:
        error_message = "YouTube API не настроен для проекта. Проверьте настройки API ключа."
    elif "403" in error_str or "forbidden" in error_str:
        error_message = "Ошибка доступа к YouTube API. Проверьте API ключ."
    elif "400" in error_str or "bad request" in error_str:
        error_message = "Некорректный запрос к YouTube API. Проверьте настройки."
    elif "500" in error_str or "internal server error" in error_str:
        error_message = "Внутренняя ошибка сервера YouTube API. Попробуйте позже."
    elif "network" in error_str or "connection" in error_str:
        error_message = "Ошибка сети при подключении к YouTube API."
    elif "timeout" in error_str:
        error_message = "Превышено время ожидания ответа от YouTube API."
    
    # Логируем детальную ошибку для отладки
    logger.error(f"Detailed error: {e}")
    return error_message

class YouTubeStatsBot:
    def __init__(self):
        self.youtube_stats = YouTubeStats()
        self.request_tracker = RequestTracker()
        logger.info("YouTubeStatsBot initialized (Simple Version)")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        
        user_id = update.effective_user.id
        
        # Проверяем лимиты запросов
        can_request, message_text = self.request_tracker.can_make_request(user_id)
        if not can_request:
            await update.message.reply_text(f"⚠️ {message_text}")
            return
        
        try:
            # Показываем сообщение о загрузке
            loading_message = await update.message.reply_text("📊 Загружаю статистику...")
            
            # Получаем сводную статистику и детальную статистику по каналам
            summary_stats = self.youtube_stats.get_summary_stats()
            today_video_stats = self.youtube_stats.get_today_video_stats()
            detailed_stats = self.youtube_stats.get_detailed_channel_stats()
            
            # Получаем статистику пользователя
            user_stats = self.request_tracker.get_user_stats(user_id)
            
            # Формируем сообщение со сводной статистикой
            message = "📊 **Статистика по отслеживаемым каналам:**\n\n"
            message += f"За сегодня: {summary_stats['today']['views']:,}👁️ | {summary_stats['today']['likes']:,}👍 | {summary_stats['today']['comments']:,}💬\n"
            
            # Добавляем детальную статистику по каналам за сегодня
            for channel_data in detailed_stats['today']:
                message += f"• {channel_data['channel_name']}: {channel_data['views']:,}👁️ | {channel_data['likes']:,}👍 | {channel_data['comments']:,}💬\n"
            
            # Проверяем наличие данных за вчера
            if 'yesterday' in summary_stats and summary_stats['yesterday']:
                message += f"\nЗа вчера: {summary_stats['yesterday']['views']:,}👁️ | {summary_stats['yesterday']['likes']:,}👍 | {summary_stats['yesterday']['comments']:,}💬\n"
                
                # Добавляем детальную статистику по каналам за вчера
                if 'yesterday' in detailed_stats and detailed_stats['yesterday']:
                    for channel_data in detailed_stats['yesterday']:
                        message += f"• {channel_data['channel_name']}: {channel_data['views']:,}👁️ | {channel_data['likes']:,}👍 | {channel_data['comments']:,}💬\n"
            else:
                message += f"\nЗа вчера: Данные временно недоступны\n"
            
            message += f"\nЗа неделю: {summary_stats['week']['views']:,}👁️ | {summary_stats['week']['likes']:,}👍 | {summary_stats['week']['comments']:,}💬\n"
            message += f"За все время: {summary_stats['all_time']['views']:,}👁️ | {summary_stats['all_time']['likes']:,}👍 | {summary_stats['all_time']['comments']:,}💬\n\n"
            message += f"📹 Видео за сегодня: {today_video_stats['uploaded']} загружено, {today_video_stats['scheduled']} в отложке\n"
            message += f"Каналов отслеживается: {len(config.CHANNELS)}\n\n"
            
            # Добавляем информацию о запросах
            message += f"📈 **Запросов: {user_stats['requests_today']}/{user_stats['requests_limit']}**\n"
            
            # Добавляем список каналов с гиперссылками
            channel_links = []
            for channel in config.CHANNELS:
                channel_name = channel['name']
                channel_username = channel.get('username', '')
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    channel_links.append(f"[{channel_name}]({channel_link})")
                else:
                    channel_links.append(channel_name)
            
            message += f"({', '.join(channel_links)})"
            
            # Создаем кнопки
            keyboard = [
                [
                    InlineKeyboardButton("За сегодня", callback_data="stats_today"),
                    InlineKeyboardButton("За вчера", callback_data="stats_yesterday")
                ],
                [
                    InlineKeyboardButton("За неделю", callback_data="stats_week"),
                    InlineKeyboardButton("За все время", callback_data="stats_all_time")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, "start")
            
            # Удаляем сообщение о загрузке и отправляем результат
            await loading_message.delete()
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводной статистики: {e}")
            await update.message.reply_text(get_error_message(e))
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        
        user_id = update.effective_user.id
        
        # Проверяем лимиты запросов
        can_request, message_text = self.request_tracker.can_make_request(user_id)
        if not can_request:
            await update.message.reply_text(f"⚠️ {message_text}")
            return
        
        await update.message.reply_text("Получаю статистику...")
        
        try:
            daily_stats = self.youtube_stats.get_daily_stats()
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, "stats")
            
            if not daily_stats:
                await update.message.reply_text("Не удалось получить статистику.")
                return
            
            # Формируем сообщение со статистикой
            message = "📊 Статистика за сегодня:\n\n"
            
            for channel_data in daily_stats:
                channel_name = channel_data['channel_name']
                channel_username = channel_data.get('channel_username', '')
                daily_views = channel_data['daily_views']
                daily_likes = channel_data['daily_likes']
                daily_comments = channel_data['daily_comments']
                videos = channel_data['videos']
                
                # Формируем гиперссылку на канал
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    message += f"📊 [{channel_name}]({channel_link}) - Статистика за сегодня\n\n"
                else:
                    message += f"📊 {channel_name} - Статистика за сегодня\n\n"
                
                # Добавляем статистику по каждому видео
                if videos:
                    message += f"📹 Видео ({len(videos)}):\n"
                    for i, video in enumerate(videos, 1):
                        title = video['title'][:40] + "..." if len(video['title']) > 40 else video['title']
                        
                        # Добавляем информацию об отложенном видео
                        if video.get('is_scheduled', False):
                            scheduled_time = video.get('scheduled_time', '')
                            message += f"{i}. {title} ⏰{scheduled_time} | {video['views']:,}👁️ {video['likes']:,}👍 {video['comments']:,}💬\n"
                        else:
                            message += f"{i}. {title} | {video['views']:,}👁️ {video['likes']:,}👍 {video['comments']:,}💬\n"
                        
                        # Добавляем комментарии к видео
                        if video.get('comment_list') and len(video['comment_list']) > 0:
                            message += "   💬 Комментарии:\n"
                            for j, comment in enumerate(video['comment_list'][:3], 1):  # Показываем только первые 3 комментария
                                message += f"      {j}. **{comment['author']}**: {comment['text']}\n"
                            if len(video['comment_list']) > 3:
                                message += f"      ... и еще {len(video['comment_list']) - 3} комментариев\n"
                            message += "\n"
                    
                    message += f"\n📈 Итого: {daily_views:,}👁️ {daily_likes:,}👍 {daily_comments:,}💬\n"
                else:
                    message += "📹 Видео за сегодня не найдены\n"
                
                message += "\n" + "─" * 30 + "\n\n"
            
            # Добавляем список каналов с гиперссылками
            message += "📺 **Отслеживаемые каналы:**\n"
            channel_links = []
            for channel in config.CHANNELS:
                channel_name = channel['name']
                channel_username = channel.get('username', '')
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    channel_links.append(f"[{channel_name}]({channel_link})")
                else:
                    channel_links.append(channel_name)
            
            message += f"({', '.join(channel_links)})"
            
            # Разбиваем сообщение на части, если оно слишком длинное
            if len(message) > 4096:
                parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
                for i, part in enumerate(parts):
                    if i == 0:
                        await update.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
                    else:
                        await update.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
            else:
                await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await update.message.reply_text(get_error_message(e))
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "stats_today":
                await self.send_period_stats(query, 1, "сегодня")
            elif query.data == "stats_yesterday":
                await self.send_period_stats(query, 2, "вчера")
            elif query.data == "stats_week":
                await self.send_period_stats(query, 7, "неделю")
            elif query.data == "stats_all_time":
                await self.send_period_stats(query, 0, "все время")
            elif query.data == "back_to_main":
                await self.show_main_menu(query)
        except Exception as e:
            logger.error(f"Ошибка при обработке кнопки: {e}")
            await query.edit_message_text(get_error_message(e))
    
    async def send_period_stats(self, query, days, period_name):
        """Отправляет статистику за указанный период"""
        user_id = query.from_user.id
        
        # Проверяем лимиты запросов
        can_request, message_text = self.request_tracker.can_make_request(user_id)
        if not can_request:
            await query.edit_message_text(f"⚠️ {message_text}")
            return
        
        await query.edit_message_text("Получаю статистику...")
        
        try:
            if days == 0:  # Все время
                stats = self.youtube_stats.get_stats_by_period(365)  # Год как приближение
            else:
                stats = self.youtube_stats.get_stats_by_period(days)
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, f"period_stats_{days}")
            
            if not stats:
                await query.edit_message_text(f"Не удалось получить статистику за {period_name}.")
                return
            
            # Формируем сообщение со статистикой
            message = f"📊 Статистика за {period_name}:\n\n"
            
            for channel_data in stats:
                channel_name = channel_data['channel_name']
                channel_username = channel_data.get('channel_username', '')
                daily_views = channel_data['daily_views']
                daily_likes = channel_data['daily_likes']
                daily_comments = channel_data['daily_comments']
                videos = channel_data['videos']
                
                # Формируем гиперссылку на канал
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    message += f"📊 [{channel_name}]({channel_link}) - Статистика за {period_name}\n\n"
                else:
                    message += f"📊 {channel_name} - Статистика за {period_name}\n\n"
                
                # Добавляем статистику по каждому видео
                if videos:
                    message += f"📹 Видео ({len(videos)}):\n"
                    for i, video in enumerate(videos, 1):
                        title = video['title'][:40] + "..." if len(video['title']) > 40 else video['title']
                        
                        # Добавляем информацию об отложенном видео
                        if video.get('is_scheduled', False):
                            scheduled_time = video.get('scheduled_time', '')
                            message += f"{i}. {title} ⏰{scheduled_time} | {video['views']:,}👁️ {video['likes']:,}👍 {video['comments']:,}💬\n"
                        else:
                            message += f"{i}. {title} | {video['views']:,}👁️ {video['likes']:,}👍 {video['comments']:,}💬\n"
                        
                        # Добавляем комментарии к видео
                        if video.get('comment_list') and len(video['comment_list']) > 0:
                            message += "   💬 Комментарии:\n"
                            for j, comment in enumerate(video['comment_list'][:3], 1):  # Показываем только первые 3 комментария
                                message += f"      {j}. **{comment['author']}**: {comment['text']}\n"
                            if len(video['comment_list']) > 3:
                                message += f"      ... и еще {len(video['comment_list']) - 3} комментариев\n"
                            message += "\n"
                    
                    message += f"\n📈 Итого: {daily_views:,}👁️ {daily_likes:,}👍 {daily_comments:,}💬\n"
                else:
                    message += "📹 Видео не найдены\n"
                
                message += "\n" + "─" * 30 + "\n\n"
            
            # Добавляем список каналов с гиперссылками
            message += "📺 **Отслеживаемые каналы:**\n"
            channel_links = []
            for channel in config.CHANNELS:
                channel_name = channel['name']
                channel_username = channel.get('username', '')
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    channel_links.append(f"[{channel_name}]({channel_link})")
                else:
                    channel_links.append(channel_name)
            
            message += f"({', '.join(channel_links)})"
            
            # Разбиваем сообщение на части, если оно слишком длинное
            if len(message) > 4096:
                # Для callback query используем только первую часть с кнопкой
                first_part = message[:4096]
                keyboard = [[InlineKeyboardButton("🏠 Домой", callback_data="back_to_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(first_part, reply_markup=reply_markup, parse_mode='Markdown')
                
                # Отправляем остальные части как новые сообщения
                remaining_parts = [message[i:i+4096] for i in range(4096, len(message), 4096)]
                for part in remaining_parts:
                    await query.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
            else:
                # Добавляем кнопку домой
                keyboard = [[InlineKeyboardButton("🏠 Домой", callback_data="back_to_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики за {period_name}: {e}")
            await query.edit_message_text(get_error_message(e))
    
    async def show_main_menu(self, query):
        """Показывает главное меню со статистикой"""
        try:
            user_id = query.from_user.id
            
            # Проверяем лимиты запросов
            can_request, message_text = self.request_tracker.can_make_request(user_id)
            if not can_request:
                await query.edit_message_text(f"⚠️ {message_text}")
                return
            
            # Получаем сводную статистику и детальную статистику по каналам
            summary_stats = self.youtube_stats.get_summary_stats()
            today_video_stats = self.youtube_stats.get_today_video_stats()
            detailed_stats = self.youtube_stats.get_detailed_channel_stats()
            
            # Получаем статистику пользователя
            user_stats = self.request_tracker.get_user_stats(user_id)
            
            # Формируем сообщение со сводной статистикой
            message = "📊 **Статистика по отслеживаемым каналам:**\n\n"
            message += f"За сегодня: {summary_stats['today']['views']:,}👁️ {summary_stats['today']['likes']:,}👍 {summary_stats['today']['comments']:,}💬\n"
            
            # Добавляем детальную статистику по каналам за сегодня
            for channel_data in detailed_stats['today']:
                message += f"• {channel_data['channel_display']}: {channel_data['views']:,} просмотров, {channel_data['likes']:,} лайков, {channel_data['comments']:,} комментов\n"
            
            # Проверяем наличие данных за вчера
            if 'yesterday' in summary_stats and summary_stats['yesterday']:
                message += f"\nЗа вчера: {summary_stats['yesterday']['views']:,}👁️ {summary_stats['yesterday']['likes']:,}👍 {summary_stats['yesterday']['comments']:,}💬\n"
                
                # Добавляем детальную статистику по каналам за вчера
                if 'yesterday' in detailed_stats and detailed_stats['yesterday']:
                    for channel_data in detailed_stats['yesterday']:
                        message += f"• {channel_data['channel_display']}: {channel_data['views']:,} просмотров, {channel_data['likes']:,} лайков, {channel_data['comments']:,} комментов\n"
            else:
                message += f"\nЗа вчера: Данные временно недоступны\n"
            
            message += f"\nЗа неделю: {summary_stats['week']['views']:,}👁️ {summary_stats['week']['likes']:,}👍 {summary_stats['week']['comments']:,}💬\n"
            message += f"За все время: {summary_stats['all_time']['views']:,}👁️ {summary_stats['all_time']['likes']:,}👍 {summary_stats['all_time']['comments']:,}💬\n\n"
            message += f"📹 Видео за сегодня: {today_video_stats['uploaded']} загружено, {today_video_stats['scheduled']} в отложке\n"
            message += f"Каналов отслеживается: {len(config.CHANNELS)}\n\n"
            
            # Добавляем информацию о запросах
            message += f"📈 **Запросов: {user_stats['requests_today']}/{user_stats['requests_limit']}**\n"
            message += f"API квота: {user_stats['api_quota_used']:,}/{user_stats['api_quota_limit']:,}\n\n"
            
            # Добавляем список каналов с гиперссылками
            channel_links = []
            for channel in config.CHANNELS:
                channel_name = channel['name']
                channel_username = channel.get('username', '')
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    channel_links.append(f"[{channel_name}]({channel_link})")
                else:
                    channel_links.append(channel_name)
            
            message += f"({', '.join(channel_links)})"
            
            # Создаем кнопки
            keyboard = [
                [
                    InlineKeyboardButton("За сегодня", callback_data="stats_today"),
                    InlineKeyboardButton("За вчера", callback_data="stats_yesterday")
                ],
                [
                    InlineKeyboardButton("За неделю", callback_data="stats_week"),
                    InlineKeyboardButton("За все время", callback_data="stats_all_time")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, "main_menu")
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводной статистики: {e}")
            await query.edit_message_text(get_error_message(e))
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        
        help_text = """
🤖 Команды бота:

/start - Главное меню со статистикой
/stats - Получить детальную статистику за сегодня
/help - Показать это сообщение

📊 Статистика включает:
• Просмотры за разные периоды
• Лайки за разные периоды
• Комментарии за разные периоды
• Количество видео за период
• Средние показатели на видео

⚠️ Лимиты:
• 15 запросов в день на пользователя
• 2 минуты между запросами
• Кэширование данных 30 минут
        """
        await update.message.reply_text(help_text)
    
    async def quota_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /quota - показывает статистику запросов"""
        user_id = update.effective_user.id
        user_stats = self.request_tracker.get_user_stats(user_id)
        
        message = "📊 **Статистика запросов:**\n\n"
        message += f"👤 **Ваши запросы:**\n"
        message += f"• Сегодня: {user_stats['requests_today']}/{user_stats['requests_limit']}\n"
        message += f"• Осталось: {user_stats['remaining_requests']}\n\n"
        message += f"🌐 **API квота:**\n"
        message += f"• Использовано: {user_stats['api_quota_used']:,}/{user_stats['api_quota_limit']:,}\n"
        message += f"• Осталось: {user_stats['api_quota_limit'] - user_stats['api_quota_used']:,}\n\n"
        message += f"⏰ **Лимиты:**\n"
        message += f"• Максимум запросов в день: {config.DAILY_REQUEST_LIMIT}\n"
        message += f"• Кулдаун между запросами: {config.REQUEST_COOLDOWN // 60} минут\n"
        message += f"• Кэширование данных: 30 минут"
        
        await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
    
    async def diagnose_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /diagnose - диагностика проблем"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь администратором
        if user_id != config.ADMIN_ID:
            await update.message.reply_text("⚠️ Эта команда доступна только администратору.")
            return
        
        await update.message.reply_text("🔍 Запускаю диагностику...")
        
        try:
            # Выполняем диагностику
            issues = self.youtube_stats.diagnose_issues()
            
            if not issues:
                message = "✅ **Диагностика завершена**\n\nВсе системы работают нормально!"
            else:
                message = "⚠️ **Найдены проблемы:**\n\n"
                for i, issue in enumerate(issues, 1):
                    message += f"{i}. {issue}\n"
                
                message += "\n🔧 **Рекомендации:**\n"
                message += "• Проверьте API ключ YouTube\n"
                message += "• Убедитесь, что API включен в Google Cloud Console\n"
                message += "• Проверьте квоту API\n"
                message += "• Убедитесь, что каналы существуют и доступны"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error during diagnosis: {e}")
            await update.message.reply_text(f"❌ Ошибка при диагностике: {str(e)}")

def main():
    """Запуск бота"""
    try:
        logger.info("Initializing YouTube Stats Bot (Simple Version)...")
        bot = YouTubeStatsBot()
        logger.info("Bot instance created successfully")
        
        # Создаем приложение
        logger.info("Creating Telegram application...")
        application = Application.builder().token(config.TELEGRAM_TOKEN).build()
        logger.info("Telegram application created successfully")
        
        # Добавляем обработчики команд
        logger.info("Adding command handlers...")
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(CommandHandler("stats", bot.stats))
        application.add_handler(CommandHandler("quota", bot.quota_command))
        application.add_handler(CommandHandler("diagnose", bot.diagnose_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        
        # Добавляем обработчик кнопок
        application.add_handler(CallbackQueryHandler(bot.button_callback))
        logger.info("All handlers added successfully")
        
        # Запускаем бота
        logger.info("Starting bot polling...")
        print("Бот запущен (простая версия)...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
