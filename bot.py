import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import os
# Выбираем конфигурацию в зависимости от среды
if os.getenv("RAILWAY_STATIC_URL"):
    import config_railway as config
else:
    import config
from youtube_stats_db import DatabaseYouTubeStats
from database import DatabaseManager
from request_tracker_db import DatabaseRequestTrackerExtended

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверяем конфигурацию при запуске
try:
    logger.info("Starting YouTube Stats Bot...")
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
    if "quotaExceeded" in str(e):
        error_message = "Превышен лимит запросов к YouTube API. Попробуйте позже."
    elif "accessNotConfigured" in str(e):
        error_message = "YouTube API не настроен для проекта. Проверьте настройки API ключа."
    elif "403" in str(e):
        error_message = "Ошибка доступа к YouTube API. Проверьте API ключ."
    return error_message

class YouTubeStatsBot:
    def __init__(self):
        # Инициализируем базу данных с путем из конфигурации
        db_path = getattr(config, 'DATABASE_PATH', 'youtube_tracker.db')
        self.db_manager = DatabaseManager(db_path)
        self.youtube_stats = DatabaseYouTubeStats(db_path)
        self.request_tracker = DatabaseRequestTrackerExtended(self.db_manager)
        
        # Мигрируем данные из JSON если необходимо
        self.youtube_stats.migrate_from_json()
        
        logger.info("YouTubeStatsBot initialized with database backend")
    
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
            
            message += f"\nЗа вчера: {summary_stats['yesterday']['views']:,}👁️ | {summary_stats['yesterday']['likes']:,}👍 | {summary_stats['yesterday']['comments']:,}💬\n"
            
            # Добавляем детальную статистику по каналам за вчера
            for channel_data in detailed_stats['yesterday']:
                message += f"• {channel_data['channel_name']}: {channel_data['views']:,}👁️ | {channel_data['likes']:,}👍 | {channel_data['comments']:,}💬\n"
            
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
    
    async def day_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /day - сводная статистика за сутки"""
        
        user_id = update.effective_user.id
        
        # Проверяем лимиты запросов
        can_request, message_text = self.request_tracker.can_make_request(user_id)
        if not can_request:
            await update.message.reply_text(f"⚠️ {message_text}")
            return
        
        await update.message.reply_text("Получаю сводную статистику за день...")
        
        try:
            daily_stats = self.youtube_stats.get_daily_stats()
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, "day_stats")
            
            if not daily_stats:
                await update.message.reply_text("Не удалось получить статистику.")
                return
            
            # Считаем общую статистику по всем каналам
            total_videos = 0
            total_views = 0
            total_likes = 0
            total_comments = 0
            
            # Формируем сводное сообщение
            message = "📈 СВОДНАЯ СТАТИСТИКА ЗА СУТКИ\n"
            message += "=" * 40 + "\n\n"
            
            # Статистика по каждому каналу
            for channel_data in daily_stats:
                channel_name = channel_data['channel_name']
                channel_username = channel_data.get('channel_username', '')
                videos = channel_data['videos']
                daily_views = channel_data['daily_views']
                daily_likes = channel_data['daily_likes']
                daily_comments = channel_data['daily_comments']
                
                video_count = len(videos)
                total_videos += video_count
                total_views += daily_views
                total_likes += daily_likes
                total_comments += daily_comments
                
                # Формируем гиперссылку на канал
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                    message += f"🎬 [{channel_name}]({channel_link})\n"
                else:
                    message += f"🎬 {channel_name}\n"
                message += f"   📹 Видео: {video_count}\n"
                message += f"   👁️ Просмотры: {daily_views:,}\n"
                message += f"   👍 Лайки: {daily_likes:,}\n"
                message += f"   💬 Комментарии: {daily_comments:,}\n\n"
            
            # Общая сводка
            message += "🏆 ОБЩАЯ СВОДКА\n"
            message += "─" * 30 + "\n"
            message += f"📹 Всего видео за день: {total_videos}\n"
            message += f"👁️ Общие просмотры: {total_views:,}\n"
            message += f"👍 Общие лайки: {total_likes:,}\n"
            message += f"💬 Общие комментарии: {total_comments:,}\n"
            
            # Средние показатели
            if total_videos > 0:
                avg_views = total_views / total_videos
                avg_likes = total_likes / total_videos
                avg_comments = total_comments / total_videos
                
                message += f"\n📊 СРЕДНИЕ ПОКАЗАТЕЛИ НА ВИДЕО:\n"
                message += f"👁️ Просмотры: {avg_views:.0f}\n"
                message += f"👍 Лайки: {avg_likes:.0f}\n"
                message += f"💬 Комментарии: {avg_comments:.0f}\n"
            
            # Добавляем список каналов с гиперссылками
            message += f"\n📺 **Отслеживаемые каналы:**\n"
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
            
            await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
                
        except Exception as e:
            logger.error(f"Ошибка при получении сводной статистики: {e}")
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
            
            message += f"\nЗа вчера: {summary_stats['yesterday']['views']:,}👁️ {summary_stats['yesterday']['likes']:,}👍 {summary_stats['yesterday']['comments']:,}💬\n"
            
            # Добавляем детальную статистику по каналам за вчера
            for channel_data in detailed_stats['yesterday']:
                message += f"• {channel_data['channel_display']}: {channel_data['views']:,} просмотров, {channel_data['likes']:,} лайков, {channel_data['comments']:,} комментов\n"
            
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
🤖 **КОМАНДЫ БОТА:**

📊 **Основные команды:**
/start - Главное меню со статистикой
/stats - Детальная статистика за сегодня
/day - Сводная статистика за сутки

📈 **Аналитика и тренды:**
/analytics - Расширенная аналитика (7 дней)
/trends - Тренды роста каналов
/quota - Статистика запросов

🛠️ **Системные команды:**
/dbstats - Статистика базы данных (админ)
/help - Показать это сообщение

💾 **Новые возможности:**
• База данных вместо JSON файлов
• Исторические данные и тренды
• Умное кэширование с разными TTL
• Batch запросы к YouTube API
• Расширенная аналитика

📊 **Что отслеживается:**
• Просмотры, лайки, комментарии
• Рост подписчиков
• Популярность видео
• Тренды по дням
• Топ контент

⚠️ **Лимиты:**
• 15 запросов в день на пользователя
• 2 минуты между запросами
• Умное кэширование (1ч/15мин/30мин)
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
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
        message += f"• Кэширование данных: умное с разными TTL"
        
        await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
    
    async def analytics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /analytics - показывает расширенную аналитику"""
        user_id = update.effective_user.id
        
        # Проверяем лимиты запросов
        can_request, message_text = self.request_tracker.can_make_request(user_id)
        if not can_request:
            await update.message.reply_text(f"⚠️ {message_text}")
            return
        
        try:
            loading_message = await update.message.reply_text("📈 Загружаю аналитику...")
            
            # Получаем аналитический дашборд
            dashboard = self.youtube_stats.get_analytics_dashboard(days=7)
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, "analytics")
            
            # Формируем сообщение
            message = "📈 **АНАЛИТИЧЕСКИЙ ДАШБОРД (7 дней)**\n"
            message += "=" * 40 + "\n\n"
            
            # Основная статистика
            summary = dashboard.get('summary', {})
            analytics = dashboard.get('analytics', {})
            
            if analytics:
                message += f"🎯 **Общие показатели:**\n"
                message += f"• Активных каналов: {analytics.get('active_channels', 0)}\n"
                message += f"• Всего видео: {analytics.get('total_videos_uploaded', 0)}\n"
                message += f"• Общие просмотры: {analytics.get('total_views', 0):,}\n"
                message += f"• Общие лайки: {analytics.get('total_likes', 0):,}\n"
                message += f"• Рост подписчиков: {analytics.get('total_subscriber_growth', 0):,}\n\n"
            
            # Топ контент
            top_content = dashboard.get('top_content', {})
            top_videos = top_content.get('top_videos', [])
            
            if top_videos:
                message += f"🏆 **Топ видео за неделю:**\n"
                for i, video in enumerate(top_videos[:3], 1):
                    title = video['title'][:30] + "..." if len(video['title']) > 30 else video['title']
                    message += f"{i}. {title}\n"
                    message += f"   📺 {video['channel_name']}: {video['views']:,} просмотров\n"
                message += "\n"
            
            # Тренды
            trends = dashboard.get('trends', {})
            if trends:
                message += f"📊 **Тренды каналов:**\n"
                for channel_name, channel_trends in list(trends.items())[:3]:
                    views_trend = channel_trends.get('total_views', [])
                    if views_trend:
                        latest = views_trend[-1]
                        growth = latest.get('growth_percentage', 0)
                        trend_emoji = "📈" if growth > 0 else "📉" if growth < 0 else "➡️"
                        message += f"{trend_emoji} {channel_name}: {growth:+.1f}%\n"
                message += "\n"
            
            message += f"💾 **База данных:**\n"
            db_stats = self.youtube_stats.get_database_stats()
            if 'database' in db_stats:
                db = db_stats['database']
                message += f"• Видео в БД: {db.get('videos_count', 0):,}\n"
                message += f"• Записей статистики: {db.get('video_stats_count', 0):,}\n"
                message += f"• Размер БД: {db.get('file_size_mb', 0)} МБ\n"
            
            await loading_message.delete()
            await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Ошибка при получении аналитики: {e}")
            await update.message.reply_text(get_error_message(e))
    
    async def trends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /trends - показывает тренды каналов"""
        user_id = update.effective_user.id
        
        # Проверяем лимиты запросов
        can_request, message_text = self.request_tracker.can_make_request(user_id)
        if not can_request:
            await update.message.reply_text(f"⚠️ {message_text}")
            return
        
        try:
            loading_message = await update.message.reply_text("📊 Анализирую тренды...")
            
            # Вычисляем тренды
            self.youtube_stats.calculate_trends(days_back=7)
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, "trends")
            
            message = "📊 **ТРЕНДЫ КАНАЛОВ (7 дней)**\n"
            message += "=" * 40 + "\n\n"
            
            # Получаем тренды для каждого канала
            for channel in config.CHANNELS[:3]:  # Показываем первые 3 канала
                channel_id = channel['channel_id']
                channel_name = channel['name']
                
                trends = self.youtube_stats.get_historical_trends(channel_id, days=7)
                
                if trends:
                    message += f"📺 **{channel_name}:**\n"
                    
                    for metric, trend_data in trends.items():
                        if trend_data:
                            latest = trend_data[-1]
                            growth = latest['growth_percentage']
                            trend_emoji = "📈" if growth > 0 else "📉" if growth < 0 else "➡️"
                            
                            metric_names = {
                                'total_views': 'Просмотры',
                                'total_likes': 'Лайки', 
                                'total_comments': 'Комментарии'
                            }
                            
                            metric_name = metric_names.get(metric, metric)
                            message += f"  {trend_emoji} {metric_name}: {growth:+.1f}% ({latest['growth_absolute']:+,})\n"
                    
                    message += "\n"
            
            await loading_message.delete()
            await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Ошибка при получении трендов: {e}")
            await update.message.reply_text(get_error_message(e))
    
    async def dbstats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /dbstats - показывает статистику базы данных"""
        user_id = update.effective_user.id
        
        # Только для админа
        if user_id != config.ADMIN_ID:
            await update.message.reply_text("❌ Эта команда доступна только администратору.")
            return
        
        try:
            db_stats = self.youtube_stats.get_database_stats()
            system_stats = self.request_tracker.get_system_stats()
            
            message = "💾 **СТАТИСТИКА БАЗЫ ДАННЫХ**\n"
            message += "=" * 40 + "\n\n"
            
            if 'database' in db_stats:
                db = db_stats['database']
                message += f"📊 **Размер и содержимое:**\n"
                message += f"• Размер файла: {db.get('file_size_mb', 0)} МБ\n"
                message += f"• Версия схемы: {db.get('schema_version', 0)}\n"
                message += f"• Пользователей: {db.get('users_count', 0):,}\n"
                message += f"• Каналов: {db.get('channels_count', 0):,}\n"
                message += f"• Видео: {db.get('videos_count', 0):,}\n"
                message += f"• Записей статистики: {db.get('video_stats_count', 0):,}\n"
                message += f"• Комментариев: {db.get('comments_count', 0):,}\n"
                message += f"• Запросов: {db.get('user_requests_count', 0):,}\n\n"
            
            if 'cache' in db_stats:
                cache = db_stats['cache']
                overall = cache.get('overall', {})
                message += f"🗄️ **Кэш:**\n"
                message += f"• Активных записей: {overall.get('active', 0):,}\n"
                message += f"• Устаревших: {overall.get('expired', 0):,}\n"
                message += f"• Всего: {overall.get('total', 0):,}\n\n"
            
            # Системная статистика за сегодня
            today = system_stats.get('today', {})
            message += f"📈 **Активность за сегодня:**\n"
            message += f"• Активных пользователей: {today.get('active_users', 0)}\n"
            message += f"• Всего запросов: {today.get('total_requests', 0)}\n"
            message += f"• API квота: {system_stats.get('api_quota', {}).get('quota_used', 0):,}\n"
            message += f"• Ошибок: {today.get('errors', 0)}\n"
            
            await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики БД: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

def main():
    """Запуск бота"""
    try:
        logger.info("Initializing YouTube Stats Bot...")
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
        application.add_handler(CommandHandler("day", bot.day_stats))
        
        application.add_handler(CommandHandler("analytics", bot.analytics_command))
        application.add_handler(CommandHandler("trends", bot.trends_command))
        application.add_handler(CommandHandler("dbstats", bot.dbstats_command))
        
        application.add_handler(CommandHandler("quota", bot.quota_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        
        # Добавляем обработчик кнопок
        application.add_handler(CallbackQueryHandler(bot.button_callback))
        logger.info("All handlers added successfully")
        
        # Запускаем бота
        logger.info("Starting bot polling...")
        print("Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
