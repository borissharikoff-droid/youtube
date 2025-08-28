#!/usr/bin/env python3
"""
Тестовый скрипт для проверки YouTube API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def test_youtube_api():
    """Тестирует подключение к YouTube API"""
    print("🔍 Тестирование YouTube API...")
    print(f"API Key: {config.YOUTUBE_API_KEY[:10]}...")
    
    try:
        # Создаем клиент API
        youtube = build('youtube', 'v3', developerKey=config.YOUTUBE_API_KEY)
        print("✅ YouTube API клиент создан успешно")
        
        # Тестируем базовый запрос
        print("\n📊 Тестирование базового запроса...")
        test_response = youtube.videos().list(
            part='snippet',
            chart='mostPopular',
            regionCode='US',
            maxResults=1
        ).execute()
        
        if test_response and 'items' in test_response:
            print("✅ Базовый запрос выполнен успешно")
            video_title = test_response['items'][0]['snippet']['title']
            print(f"📹 Получено видео: {video_title}")
        else:
            print("❌ Базовый запрос вернул пустой ответ")
            return False
        
        # Тестируем каналы из конфигурации
        print(f"\n📺 Тестирование {len(config.CHANNELS)} каналов...")
        
        for i, channel in enumerate(config.CHANNELS, 1):
            channel_id = channel['channel_id']
            channel_name = channel['name']
            
            print(f"\n{i}. Тестирование канала: {channel_name}")
            
            try:
                channel_response = youtube.channels().list(
                    part='snippet,statistics',
                    id=channel_id
                ).execute()
                
                if channel_response.get('items'):
                    channel_info = channel_response['items'][0]
                    actual_name = channel_info['snippet']['title']
                    subscriber_count = channel_info['statistics'].get('subscriberCount', 'N/A')
                    
                    print(f"   ✅ Канал найден: {actual_name}")
                    print(f"   👥 Подписчиков: {subscriber_count}")
                else:
                    print(f"   ❌ Канал не найден: {channel_id}")
                    
            except HttpError as e:
                if e.resp.status == 403:
                    print(f"   ❌ Ошибка доступа (403): {e}")
                elif e.resp.status == 404:
                    print(f"   ❌ Канал не найден (404): {e}")
                else:
                    print(f"   ❌ Ошибка HTTP {e.resp.status}: {e}")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
        
        print("\n✅ Тестирование завершено успешно!")
        return True
        
    except HttpError as e:
        print(f"❌ Ошибка HTTP: {e}")
        if e.resp.status == 403:
            print("🔧 Возможные причины:")
            print("   • API ключ недействителен")
            print("   • YouTube Data API v3 не включен в проекте")
            print("   • Превышена квота API")
        elif e.resp.status == 400:
            print("🔧 Возможные причины:")
            print("   • Некорректный API ключ")
            print("   • Неправильный формат запроса")
        return False
        
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        return False

async def test_telegram_bot():
    """Тестирует Telegram бота"""
    print("\n🤖 Тестирование Telegram бота...")
    print(f"Bot Token: {config.TELEGRAM_TOKEN[:10]}...")
    
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_TOKEN)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"✅ Бот подключен: @{bot_info.username}")
        print(f"📝 Имя бота: {bot_info.first_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка Telegram бота: {e}")
        return False

async def main():
    print("🚀 Запуск тестирования YouTube Analytics Bot...")
    print("=" * 50)
    
    # Тестируем YouTube API
    youtube_ok = test_youtube_api()
    
    # Тестируем Telegram бота
    telegram_ok = await test_telegram_bot()
    
    print("\n" + "=" * 50)
    print("📋 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"YouTube API: {'✅ Работает' if youtube_ok else '❌ Ошибка'}")
    print(f"Telegram Bot: {'✅ Работает' if telegram_ok else '❌ Ошибка'}")
    
    if youtube_ok and telegram_ok:
        print("\n🎉 Все системы работают нормально!")
        print("Бот готов к использованию.")
    else:
        print("\n⚠️ Обнаружены проблемы:")
        if not youtube_ok:
            print("• Проверьте YouTube API ключ и настройки")
        if not telegram_ok:
            print("• Проверьте Telegram Bot Token")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
