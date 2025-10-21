#!/usr/bin/env python3
"""
Тестовый скрипт для проверки валидности каналов YouTube
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from youtube_stats import YouTubeStats
from channel_manager import channel_manager
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_channels():
    """Тестирует все каналы в системе"""
    print("🔍 Тестирование каналов YouTube...")
    print("=" * 50)
    
    try:
        youtube_stats = YouTubeStats()
        channels = channel_manager.get_channels()
        
        if not channels:
            print("❌ Нет каналов для тестирования")
            return
        
        print(f"📺 Найдено каналов: {len(channels)}")
        print()
        
        for i, channel in enumerate(channels, 1):
            channel_name = channel['name']
            channel_id = channel.get('channel_id', '')
            username = channel.get('username', '')
            
            print(f"{i}. 📺 {channel_name}")
            print(f"   Channel ID: {channel_id or 'НЕТ'}")
            print(f"   Username: {username or 'НЕТ'}")
            
            if not channel_id:
                print("   ❌ Нет Channel ID")
                continue
            
            # Тестируем доступ к каналу
            try:
                channel_stats = youtube_stats.get_channel_stats(channel_id)
                if channel_stats:
                    print(f"   ✅ Канал доступен")
                    print(f"   👥 Подписчики: {channel_stats['subscribers']:,}")
                    print(f"   👁️ Просмотры: {channel_stats['total_views']:,}")
                    print(f"   🎬 Видео: {channel_stats['total_videos']:,}")
                else:
                    print("   ❌ Не удалось получить статистику канала")
            except Exception as e:
                print(f"   ❌ Ошибка: {str(e)}")
            
            print()
        
        # Тестируем общее подключение к API
        print("🔗 Тестирование подключения к YouTube API...")
        api_ok, api_message = youtube_stats.test_api_connection()
        if api_ok:
            print(f"✅ {api_message}")
        else:
            print(f"❌ {api_message}")
        
        print()
        print("🎯 Тестирование завершено!")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}")
        print(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    test_channels()
