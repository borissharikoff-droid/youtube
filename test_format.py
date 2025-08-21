#!/usr/bin/env python3
"""
Тестовый скрипт для проверки нового формата сообщения
"""

from youtube_stats import YouTubeStats
import config

def test_new_format():
    """Тестирует новый формат сообщения"""
    youtube_stats = YouTubeStats()
    
    print("Тестируем новый формат сообщения...")
    
    try:
        # Получаем данные
        summary_stats = youtube_stats.get_summary_stats()
        today_video_stats = youtube_stats.get_today_video_stats()
        detailed_stats = youtube_stats.get_detailed_channel_stats()
        
        print("\n" + "="*50)
        print("НОВЫЙ ФОРМАТ СООБЩЕНИЯ:")
        print("="*50)
        
        # Формируем сообщение в новом формате
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
        
        # Добавляем информацию о запросах (тестовые данные)
        message += f"📈 **Запросов: 5/15**\n"
        message += f"API квота: 1,234/10,000\n\n"
        
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
        
        print(message)
        print("\n" + "="*50)
        print("Тест завершен успешно!")
        
    except Exception as e:
        print(f"Ошибка при тестировании: {e}")

if __name__ == "__main__":
    test_new_format()
