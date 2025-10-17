import logging
from datetime import datetime, timedelta, timezone
import sys
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import config
from youtube_stats import YouTubeStats
from request_tracker import RequestTracker
from channel_manager import channel_manager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Формирует ссылку на канал: по @username или по channel_id
def build_channel_link(channel: dict) -> str:
    channel_username = channel.get('username', '') or ''
    channel_id = channel.get('channel_id', '') or ''
    
    if channel_username:
        # Очищаем username от лишних символов и URL
        clean_username = channel_username.strip()
        
        # Если это уже полная ссылка, возвращаем как есть
        if clean_username.startswith('https://www.youtube.com/'):
            return clean_username
        
        # Убираем @ если есть
        if clean_username.startswith('@'):
            clean_username = clean_username[1:]
        
        # Проверяем, что username не содержит недопустимых символов
        if clean_username and not clean_username.startswith('http'):
            return f"https://www.youtube.com/@{clean_username}"
    
    if channel_id:
        return f"https://www.youtube.com/channel/{channel_id}"
    
    return ""

# Проверяем конфигурацию при запуске
try:
    logger.info("Starting YouTube Stats Bot for Railway...")
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
        # Кэш для главного меню
        self._main_menu_cache = {}
        self._cache_timeout = 3600  # 1 час
        logger.info("YouTubeStatsBot initialized for Railway")
    
    def _get_cached_main_menu(self):
        """Получает кэшированные данные главного меню"""
        import time
        if 'data' in self._main_menu_cache:
            timestamp, data = self._main_menu_cache['data']
            if time.time() - timestamp < self._cache_timeout:
                logger.info("Используем кэшированные данные главного меню")
                return data
        return None
    
    def _set_cached_main_menu(self, data):
        """Сохраняет данные главного меню в кэш"""
        import time
        self._main_menu_cache['data'] = (time.time(), data)
        logger.info("Данные главного меню сохранены в кэш")
    
    def _clear_main_menu_cache(self):
        """Очищает кэш главного меню"""
        self._main_menu_cache.clear()
        logger.info("Кэш главного меню очищен")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        
        user_id = update.effective_user.id
        
        # Проверяем лимиты запросов
        can_request, message_text = self.request_tracker.can_make_request(user_id)
        if not can_request:
            await update.message.reply_text(f"⚠️ {message_text}")
            return
        
        try:
            # Проверяем кэш
            cached_data = self._get_cached_main_menu()
            if cached_data:
                # Используем кэшированные данные
                message = cached_data['message']
                reply_markup = cached_data['reply_markup']
                
                # Записываем запрос
                self.request_tracker.record_request(user_id, "start")
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
                return
            
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
            now_utc = datetime.now(timezone.utc)
            today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_date = (today_start - timedelta(days=1)).date()
            
            # Неделя с понедельника по воскресенье
            current_weekday = now_utc.weekday()  # 0=понедельник, 6=воскресенье
            week_start_date = (today_start - timedelta(days=current_weekday)).date()
            week_end_date = week_start_date + timedelta(days=6)
            message += (
                f"За сегодня: {summary_stats['today']['views']:,}👁️ | "
                f"{summary_stats['today']['likes']:,}👍 | {summary_stats['today']['comments']:,}💬 | "
                f"+{summary_stats['today'].get('subs_gain', 0):,}👤 | {summary_stats['today'].get('video_count', 0):,}🎬\n"
            )
            
            # Добавляем пояснение о логике подсчета
            if summary_stats['today']['views'] == 0:
                message += "ℹ️ *Показаны видео, опубликованные сегодня*\n"
            
            # Добавляем детальную статистику по каналам за сегодня
            for channel_data in detailed_stats['today']:
                message += (
                    f"• {channel_data['channel_name']}: {channel_data['views']:,}👁️ | "
                    f"{channel_data['likes']:,}👍 | {channel_data['comments']:,}💬\n"
                )
            
            # Проверяем наличие данных за вчера
            if 'yesterday' in summary_stats and summary_stats['yesterday']:
                message += (
                    f"\nЗа вчера (UTC {yesterday_date}): {summary_stats['yesterday']['views']:,}👁️ | "
                    f"{summary_stats['yesterday']['likes']:,}👍 | {summary_stats['yesterday']['comments']:,}💬 | "
                    f"+{summary_stats['yesterday'].get('subs_gain', 0):,}👤 | {summary_stats['yesterday'].get('video_count', 0):,}🎬\n"
                )
                
                # Добавляем детальную статистику по каналам за вчера
                if 'yesterday' in detailed_stats and detailed_stats['yesterday']:
                    for channel_data in detailed_stats['yesterday']:
                        message += (
                            f"• {channel_data['channel_name']}: {channel_data['views']:,}👁️ | "
                            f"{channel_data['likes']:,}👍 | {channel_data['comments']:,}💬\n"
                        )
            else:
                message += f"\nЗа вчера: Данные временно недоступны\n"
            
            message += (
                f"\nЗа неделю (UTC {week_start_date} — {week_end_date}): {summary_stats['week']['views']:,}👁️ | "
                f"{summary_stats['week']['likes']:,}👍 | {summary_stats['week']['comments']:,}💬 | "
                f"+{summary_stats['week'].get('subs_gain', 0):,}👤 | {summary_stats['week'].get('video_count', 0):,}🎬\n"
            )
            message += (
                f"За все время: {summary_stats['all_time']['views']:,}👁️ | "
                f"{summary_stats['all_time']['likes']:,}👍 | {summary_stats['all_time']['comments']:,}💬 | "
                f"{summary_stats['all_time'].get('subscribers', 0):,}👤 | {summary_stats['all_time'].get('videos', 0):,}🎬\n\n"
            )
            channels = channel_manager.get_channels()
            message += f"Каналов отслеживается: {len(channels)}\n\n"
            
            # Убираем строку с количеством запросов по просьбе пользователя
            
            # Добавляем список каналов с гиперссылками
            channel_links = []
            for channel in channels:
                channel_name = channel['name']
                channel_link = build_channel_link(channel)
                if channel_link:
                    channel_links.append(f"[{channel_name}]({channel_link})")
                else:
                    channel_links.append(channel_name)
            
            message += f"({', '.join(channel_links)})"
            
            # Создаем кнопки управления каналами
            keyboard = [
                [
                    InlineKeyboardButton("➕ Добавить канал", callback_data="add_channel"),
                    InlineKeyboardButton("➖ Удалить канал", callback_data="remove_channel")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Записываем запрос
            self.request_tracker.record_request(user_id, "start")
            
            # Сохраняем в кэш
            self._set_cached_main_menu({
                'message': message,
                'reply_markup': reply_markup
            })
            
            # Удаляем сообщение о загрузке и отправляем результат
            await loading_message.delete()
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводной статистики: {e}")
            # Удаляем loading сообщение если оно есть
            try:
                if 'loading_message' in locals():
                    await loading_message.delete()
            except:
                pass
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
                channel_link = ''
                if channel_username:
                    channel_link = f"https://www.youtube.com/{channel_username}"
                # Попытка собрать ссылку по channel_id, если username нет в данных
                if not channel_link:
                    channel_id = channel_data.get('channel_id', '')
                    if channel_id:
                        channel_link = f"https://www.youtube.com/channel/{channel_id}"
                if channel_link:
                    message += f"📊 [{channel_name}]({channel_link}) - Статистика за сегодня\n\n"
                else:
                    message += f"📊 {channel_name} - Статистика за сегодня\n\n"
                
                # Добавляем статистику по каждому видео
                if videos:
                    message += f"📹 Видео ({len(videos)}):\n"
                    for i, video in enumerate(videos, 1):
                        title = video['title'][:40] + "..." if len(video['title']) > 40 else video['title']
                        message += f"{i}. {title} | {video['views']:,}👁️ {video['likes']:,}👍 {video['comments']:,}💬\n"
                    
                    message += f"\n📈 Итого: {daily_views:,}👁️ {daily_likes:,}👍 {daily_comments:,}💬\n"
                else:
                    message += "📹 Видео за сегодня не найдены\n"
                
                message += "\n" + "─" * 30 + "\n\n"
            
            # Разбиваем сообщение на части, если оно слишком длинное
            if len(message) > 4096:
                parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
                for part in parts:
                    await update.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
            else:
                await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await update.message.reply_text(get_error_message(e))
    
    async def test_channels_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /test_channels - тестирует поиск каналов"""
        user_id = update.effective_user.id
        
        # Только для админа
        if user_id != config.ADMIN_ID:
            await update.message.reply_text("❌ Эта команда доступна только администратору.")
            return
        
        try:
            message = "🔍 **Тестирование поиска каналов:**\n\n"
            
            for channel in config.CHANNELS:
                channel_name = channel['name']
                channel_id = channel.get('channel_id', '')
                username = channel.get('username', '')
                
                message += f"📺 **{channel_name}**\n"
                message += f"• channel_id: `{channel_id or 'НЕТ'}`\n"
                message += f"• username: `{username or 'НЕТ'}`\n"
                
                if not channel_id and username:
                    # Тестируем поиск
                    resolved_id = self.youtube_stats._resolve_channel_id_by_username(username)
                    if resolved_id:
                        message += f"• ✅ Найден: `{resolved_id}`\n"
                    else:
                        message += f"• ❌ Не найден\n"
                
                message += "\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при тестировании каналов: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        
        help_text = """
🤖 **YouTube Analytics Bot**

**Команды:**
/start - Главное меню со статистикой
/stats - Детальная статистика за сегодня
/test_channels - Тестирование поиска каналов (админ)
/help - Показать это сообщение

**Статистика включает:**
• Просмотры, лайки, комментарии
• Количество видео за период
• Отслеживание по каналам

**Важно:**
• "За сегодня/вчера" = видео, опубликованные в этот день
• Время рассчитывается по UTC
• Данные кэшируются 30 минут

**Лимиты:**
• 15 запросов в день на пользователя
• 2 минуты между запросами
• Кэширование данных 30 минут

🚀 **Развернуто на Railway**
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback запросов от inline кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Проверяем права доступа (только админ может управлять каналами)
        if user_id != config.ADMIN_ID:
            await query.edit_message_text("❌ Управление каналами доступно только администратору.")
            return
        
        if query.data == "add_channel":
            await self.show_add_channel_menu(query, context)
        elif query.data == "remove_channel":
            await self.show_remove_channel_menu(query, context)
        elif query.data.startswith("confirm_add_"):
            await self.confirm_add_channel(query, context)
        elif query.data.startswith("confirm_remove_"):
            await self.confirm_remove_channel(query, context)
        elif query.data == "back_to_main":
            await self.back_to_main_menu(query, context)
    
    async def show_add_channel_menu(self, query, context):
        """Показывает меню добавления канала"""
        message = """
➕ **Добавление канала для отслеживания**

Отправьте мне:
1. **Название канала** (например: "Мой канал")
2. **Username канала** (например: @my_channel или my_channel)
3. **Channel ID** (опционально, если известен)

Пример:
```
Название: Тестовый канал
Username: @test_channel
```

Или просто отправьте username канала, и я попробую найти его автоматически.
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Устанавливаем состояние ожидания ввода
        context.user_data['waiting_for_channel_info'] = True
        context.user_data['action'] = 'add_channel'
    
    async def show_remove_channel_menu(self, query, context):
        """Показывает меню удаления канала"""
        channels = channel_manager.get_channels()
        
        if not channels:
            message = "❌ Нет каналов для удаления."
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
        else:
            message = "➖ **Удаление канала из отслеживания**\n\nВыберите канал для удаления:\n\n"
            
            keyboard = []
            for i, channel in enumerate(channels):
                channel_name = channel['name']
                keyboard.append([InlineKeyboardButton(
                    f"🗑️ {channel_name}", 
                    callback_data=f"confirm_remove_{i}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def confirm_add_channel(self, query, context):
        """Подтверждает добавление канала"""
        # Здесь будет логика подтверждения добавления
        await query.edit_message_text("✅ Канал успешно добавлен!")
    
    async def confirm_remove_channel(self, query, context):
        """Подтверждает удаление канала"""
        channel_index = int(query.data.split("_")[-1])
        result = channel_manager.remove_channel(channel_index)
        
        if result['success']:
            # Очищаем кэш главного меню, так как список каналов изменился
            self._clear_main_menu_cache()
            
            # Добавляем кнопку "Назад" после успешного удаления
            keyboard = [[InlineKeyboardButton("🔙 Назад к меню", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"✅ {result['message']}", reply_markup=reply_markup)
        else:
            # Добавляем кнопку "Назад" даже при ошибке
            keyboard = [[InlineKeyboardButton("🔙 Назад к меню", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"❌ {result['message']}", reply_markup=reply_markup)
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений для добавления каналов"""
        user_id = update.effective_user.id
        
        # Проверяем права доступа
        if user_id != config.ADMIN_ID:
            return
        
        # Проверяем, ожидаем ли мы информацию о канале
        if not context.user_data.get('waiting_for_channel_info', False):
            return
        
        action = context.user_data.get('action')
        if action == 'add_channel':
            await self.process_channel_info(update, context)
    
    async def process_channel_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает информацию о канале для добавления"""
        text = update.message.text.strip()
        
        try:
            # Парсим информацию о канале
            channel_info = self.parse_channel_info(text)
            
            if not channel_info['name']:
                await update.message.reply_text(
                    "❌ Не удалось определить название канала. Попробуйте еще раз или отправьте /cancel для отмены."
                )
                return
            
            # Пытаемся найти channel_id если он не указан
            if not channel_info['channel_id'] and channel_info['username']:
                try:
                    resolved_id = self.youtube_stats._resolve_channel_id_by_username(channel_info['username'])
                    if resolved_id:
                        channel_info['channel_id'] = resolved_id
                        await update.message.reply_text(f"✅ Найден Channel ID: {resolved_id}")
                except Exception as e:
                    logger.warning(f"Не удалось найти channel_id для {channel_info['username']}: {e}")
            
            # Добавляем канал
            result = channel_manager.add_channel(
                name=channel_info['name'],
                username=channel_info['username'],
                channel_id=channel_info['channel_id']
            )
            
            if result['success']:
                # Очищаем кэш главного меню, так как список каналов изменился
                self._clear_main_menu_cache()
                
                # Очищаем состояние ожидания
                context.user_data.pop('waiting_for_channel_info', None)
                context.user_data.pop('action', None)
                
                # Показываем успешное сообщение с кнопкой возврата
                keyboard = [[InlineKeyboardButton("🔙 Назад к меню", callback_data="back_to_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                message = f"✅ {result['message']}\n\n"
                channel = result['channel']
                message += f"📺 **Название:** {channel['name']}\n"
                if channel['username']:
                    message += f"👤 **Username:** {channel['username']}\n"
                if channel['channel_id']:
                    message += f"🆔 **Channel ID:** {channel['channel_id']}\n"
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ {result['message']}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке информации о канале: {e}")
            await update.message.reply_text("❌ Произошла ошибка при добавлении канала. Попробуйте еще раз.")
    
    def parse_channel_info(self, text: str) -> dict:
        """Парсит информацию о канале из текста"""
        channel_info = {
            'name': '',
            'username': '',
            'channel_id': ''
        }
        
        # Убираем лишние пробелы и переносы строк
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Пытаемся найти структурированную информацию
        name_match = re.search(r'название[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if name_match:
            channel_info['name'] = name_match.group(1).strip()
        
        username_match = re.search(r'username[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if username_match:
            channel_info['username'] = username_match.group(1).strip()
        
        channel_id_match = re.search(r'channel[_\s]*id[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if channel_id_match:
            channel_info['channel_id'] = channel_id_match.group(1).strip()
        
        # Если структурированной информации нет, пытаемся извлечь из простого текста
        if not channel_info['name'] and not channel_info['username']:
            # Проверяем, является ли текст URL
            if text.startswith('https://www.youtube.com/'):
                # Извлекаем username из URL
                if '/@' in text:
                    username_part = text.split('/@')[1]
                    if '/' in username_part:
                        username_part = username_part.split('/')[0]
                    channel_info['username'] = f"@{username_part}"
                    channel_info['name'] = username_part.replace('_', ' ').replace('-', ' ').title()
                else:
                    # Это может быть channel ID
                    channel_info['channel_id'] = text.split('/')[-1]
                    channel_info['name'] = "Канал"
            # Проверяем, является ли текст username (начинается с @ или содержит только буквы/цифры/подчеркивания)
            elif re.match(r'^@?[a-zA-Z0-9_-]+$', text):
                channel_info['username'] = text
                # Пытаемся извлечь название из username
                clean_username = text.lstrip('@')
                channel_info['name'] = clean_username.replace('_', ' ').replace('-', ' ').title()
            else:
                # Считаем весь текст названием канала
                channel_info['name'] = text
        
        # Если есть только username, но нет названия
        if channel_info['username'] and not channel_info['name']:
            clean_username = channel_info['username'].lstrip('@')
            channel_info['name'] = clean_username.replace('_', ' ').replace('-', ' ').title()
        
        return channel_info
    
    async def back_to_main_menu(self, query, context):
        """Возвращает к главному меню"""
        # Очищаем состояние ожидания
        context.user_data.pop('waiting_for_channel_info', None)
        context.user_data.pop('action', None)
        
        # Получаем статистику для главного меню
        try:
            # Проверяем кэш
            cached_data = self._get_cached_main_menu()
            if cached_data:
                # Используем кэшированные данные
                message = cached_data['message']
                reply_markup = cached_data['reply_markup']
                await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
                return
            
            summary_stats = self.youtube_stats.get_summary_stats()
            today_video_stats = self.youtube_stats.get_today_video_stats()
            detailed_stats = self.youtube_stats.get_detailed_channel_stats()
            
            # Формируем сообщение со сводной статистикой
            message = "📊 **Статистика по отслеживаемым каналам:**\n\n"
            now_utc = datetime.now(timezone.utc)
            today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_date = (today_start - timedelta(days=1)).date()
            
            # Неделя с понедельника по воскресенье
            current_weekday = now_utc.weekday()  # 0=понедельник, 6=воскресенье
            week_start_date = (today_start - timedelta(days=current_weekday)).date()
            week_end_date = week_start_date + timedelta(days=6)
            message += (
                f"За сегодня: {summary_stats['today']['views']:,}👁️ | "
                f"{summary_stats['today']['likes']:,}👍 | {summary_stats['today']['comments']:,}💬 | "
                f"+{summary_stats['today'].get('subs_gain', 0):,}👤 | {summary_stats['today'].get('video_count', 0):,}🎬\n"
            )
            
            # Добавляем пояснение о логике подсчета
            if summary_stats['today']['views'] == 0:
                message += "ℹ️ *Показаны видео, опубликованные сегодня*\n"
            
            # Добавляем детальную статистику по каналам за сегодня
            for channel_data in detailed_stats['today']:
                message += (
                    f"• {channel_data['channel_name']}: {channel_data['views']:,}👁️ | "
                    f"{channel_data['likes']:,}👍 | {channel_data['comments']:,}💬\n"
                )
            
            # Проверяем наличие данных за вчера
            if 'yesterday' in summary_stats and summary_stats['yesterday']:
                message += (
                    f"\nЗа вчера (UTC {yesterday_date}): {summary_stats['yesterday']['views']:,}👁️ | "
                    f"{summary_stats['yesterday']['likes']:,}👍 | {summary_stats['yesterday']['comments']:,}💬 | "
                    f"+{summary_stats['yesterday'].get('subs_gain', 0):,}👤 | {summary_stats['yesterday'].get('video_count', 0):,}🎬\n"
                )
                
                # Добавляем детальную статистику по каналам за вчера
                if 'yesterday' in detailed_stats and detailed_stats['yesterday']:
                    for channel_data in detailed_stats['yesterday']:
                        message += (
                            f"• {channel_data['channel_name']}: {channel_data['views']:,}👁️ | "
                            f"{channel_data['likes']:,}👍 | {channel_data['comments']:,}💬\n"
                        )
            else:
                message += f"\nЗа вчера: Данные временно недоступны\n"
            
            message += (
                f"\nЗа неделю (UTC {week_start_date} — {week_end_date}): {summary_stats['week']['views']:,}👁️ | "
                f"{summary_stats['week']['likes']:,}👍 | {summary_stats['week']['comments']:,}💬 | "
                f"+{summary_stats['week'].get('subs_gain', 0):,}👤 | {summary_stats['week'].get('video_count', 0):,}🎬\n"
            )
            message += (
                f"За все время: {summary_stats['all_time']['views']:,}👁️ | "
                f"{summary_stats['all_time']['likes']:,}👍 | {summary_stats['all_time']['comments']:,}💬 | "
                f"{summary_stats['all_time'].get('subscribers', 0):,}👤 | {summary_stats['all_time'].get('videos', 0):,}🎬\n\n"
            )
            channels = channel_manager.get_channels()
            message += f"Каналов отслеживается: {len(channels)}\n\n"
            
            # Добавляем список каналов с гиперссылками
            channel_links = []
            for channel in channels:
                channel_name = channel['name']
                channel_link = build_channel_link(channel)
                if channel_link:
                    channel_links.append(f"[{channel_name}]({channel_link})")
                else:
                    channel_links.append(channel_name)
            
            message += f"({', '.join(channel_links)})"
            
            # Создаем кнопки управления каналами
            keyboard = [
                [
                    InlineKeyboardButton("➕ Добавить канал", callback_data="add_channel"),
                    InlineKeyboardButton("➖ Удалить канал", callback_data="remove_channel")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Сохраняем в кэш
            self._set_cached_main_menu({
                'message': message,
                'reply_markup': reply_markup
            })
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Ошибка при возврате к главному меню: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке статистики.")

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
        application.add_handler(CommandHandler("test_channels", bot.test_channels_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        
        # Добавляем обработчик callback запросов
        application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
        
        # Добавляем обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text_message))
        
        logger.info("All handlers added successfully")
        
        # Запускаем бота
        logger.info("Starting bot polling...")
        print("🚀 Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
