#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функции build_channel_link
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot import build_channel_link
from channel_manager import channel_manager

def test_channel_links():
    """Тестирует функцию build_channel_link"""
    print("🔗 Тестирование функции build_channel_link...")
    print("=" * 50)
    
    # Получаем каналы
    channels = channel_manager.get_channels()
    
    print(f"📺 Тестируем {len(channels)} каналов:")
    print()
    
    for i, channel in enumerate(channels, 1):
        channel_name = channel['name']
        channel_id = channel.get('channel_id', '')
        username = channel.get('username', '')
        
        print(f"{i}. 📺 {channel_name}")
        print(f"   Channel ID: {channel_id or 'НЕТ'}")
        print(f"   Username: {username or 'НЕТ'}")
        
        # Тестируем функцию build_channel_link
        link = build_channel_link(channel)
        print(f"   🔗 Сгенерированная ссылка: {link}")
        
        # Проверяем валидность ссылки
        if link:
            if link.startswith('https://www.youtube.com/channel/'):
                print("   ✅ Ссылка на канал по Channel ID")
            elif link.startswith('https://www.youtube.com/@'):
                print("   ✅ Ссылка на канал по Username")
            else:
                print("   ⚠️ Неожиданный формат ссылки")
        else:
            print("   ❌ Ссылка не сгенерирована")
        
        print()
    
    # Тестируем различные сценарии
    print("🧪 Тестирование различных сценариев:")
    print()
    
    test_cases = [
        {
            "name": "Тест 1: Только Channel ID",
            "channel": {"name": "Тест 1", "channel_id": "UC1234567890123456789012", "username": ""}
        },
        {
            "name": "Тест 2: Только Username с @",
            "channel": {"name": "Тест 2", "channel_id": "", "username": "@testuser"}
        },
        {
            "name": "Тест 3: Username без @",
            "channel": {"name": "Тест 3", "channel_id": "", "username": "testuser"}
        },
        {
            "name": "Тест 4: Полная ссылка в username",
            "channel": {"name": "Тест 4", "channel_id": "", "username": "https://www.youtube.com/@testuser"}
        },
        {
            "name": "Тест 5: Пустые данные",
            "channel": {"name": "Тест 5", "channel_id": "", "username": ""}
        },
        {
            "name": "Тест 6: Channel ID и Username",
            "channel": {"name": "Тест 6", "channel_id": "UC1234567890123456789012", "username": "@testuser"}
        }
    ]
    
    for test_case in test_cases:
        print(f"   {test_case['name']}:")
        link = build_channel_link(test_case['channel'])
        print(f"   🔗 Результат: {link}")
        print()
    
    print("🎯 Тестирование функции build_channel_link завершено!")

if __name__ == "__main__":
    test_channel_links()
