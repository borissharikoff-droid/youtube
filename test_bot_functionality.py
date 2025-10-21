#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности бота
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from channel_manager import channel_manager
import json

def test_bot_functionality():
    """Тестирует основную функциональность бота"""
    print("🤖 Тестирование функциональности бота...")
    print("=" * 50)
    
    # Тест 1: Загрузка каналов
    print("1. 📺 Загрузка каналов из конфигурации:")
    try:
        channels = channel_manager.get_channels()
        print(f"   ✅ Загружено каналов: {len(channels)}")
        
        for i, channel in enumerate(channels, 1):
            print(f"   {i}. {channel['name']}")
            print(f"      Channel ID: {channel.get('channel_id', 'НЕТ')}")
            print(f"      Username: {channel.get('username', 'НЕТ')}")
        
        # Проверяем, что у нас есть правильные каналы
        expected_channels = ["Говорилки софтом", "Премия дарвина", "Милитари"]
        actual_names = [ch['name'] for ch in channels]
        
        if set(expected_channels) == set(actual_names):
            print("   ✅ Все ожидаемые каналы найдены")
        else:
            print("   ❌ Не все ожидаемые каналы найдены")
            print(f"   Ожидаемые: {expected_channels}")
            print(f"   Фактические: {actual_names}")
            
    except Exception as e:
        print(f"   ❌ Ошибка при загрузке каналов: {e}")
    
    print()
    
    # Тест 2: Проверка файла конфигурации
    print("2. 📁 Проверка файла конфигурации:")
    try:
        with open('channels_config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            print(f"   ✅ Файл конфигурации загружен")
            print(f"   📅 Последнее обновление: {config_data.get('last_updated', 'НЕТ')}")
            print(f"   📺 Каналов в файле: {len(config_data.get('channels', []))}")
            
            # Проверяем структуру данных
            for channel in config_data.get('channels', []):
                if 'name' not in channel:
                    print("   ❌ Канал без имени")
                if 'channel_id' not in channel:
                    print("   ❌ Канал без channel_id")
                if 'username' not in channel:
                    print("   ❌ Канал без username")
                    
    except Exception as e:
        print(f"   ❌ Ошибка при чтении файла конфигурации: {e}")
    
    print()
    
    # Тест 3: Тестирование добавления канала
    print("3. ➕ Тестирование добавления канала:")
    try:
        result = channel_manager.add_channel(
            name="Тестовый канал для проверки",
            username="@test_channel",
            channel_id="UCtest123456789"
        )
        
        if result['success']:
            print(f"   ✅ {result['message']}")
            
            # Удаляем тестовый канал
            channels = channel_manager.get_channels()
            test_index = -1
            for i, channel in enumerate(channels):
                if channel['name'] == "Тестовый канал для проверки":
                    test_index = i
                    break
            
            if test_index >= 0:
                remove_result = channel_manager.remove_channel(test_index)
                if remove_result['success']:
                    print("   ✅ Тестовый канал удален")
                else:
                    print(f"   ❌ Ошибка при удалении: {remove_result['message']}")
        else:
            print(f"   ❌ {result['message']}")
            
    except Exception as e:
        print(f"   ❌ Ошибка при тестировании добавления: {e}")
    
    print()
    
    # Тест 4: Проверка валидности Channel ID
    print("4. 🔍 Проверка валидности Channel ID:")
    channels = channel_manager.get_channels()
    for channel in channels:
        channel_id = channel.get('channel_id', '')
        if channel_id:
            # Проверяем формат Channel ID (должен начинаться с UC и содержать 24 символа)
            if channel_id.startswith('UC') and len(channel_id) == 24:
                print(f"   ✅ {channel['name']}: Channel ID валиден")
            else:
                print(f"   ❌ {channel['name']}: Channel ID невалиден ({channel_id})")
        else:
            print(f"   ⚠️ {channel['name']}: Channel ID отсутствует")
    
    print()
    print("🎯 Тестирование функциональности бота завершено!")

if __name__ == "__main__":
    test_bot_functionality()
