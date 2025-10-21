#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности channel_manager
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from channel_manager import channel_manager
import json

def test_channel_manager():
    """Тестирует функциональность channel_manager"""
    print("🔍 Тестирование Channel Manager...")
    print("=" * 50)
    
    # Тест 1: Получение текущих каналов
    print("1. 📺 Получение текущих каналов:")
    channels = channel_manager.get_channels()
    print(f"   Найдено каналов: {len(channels)}")
    for i, channel in enumerate(channels, 1):
        print(f"   {i}. {channel['name']} (ID: {channel.get('channel_id', 'НЕТ')})")
    print()
    
    # Тест 2: Добавление тестового канала
    print("2. ➕ Добавление тестового канала:")
    result = channel_manager.add_channel(
        name="Тестовый канал",
        username="@test_channel",
        channel_id="UCtest123456789"
    )
    if result['success']:
        print(f"   ✅ {result['message']}")
    else:
        print(f"   ❌ {result['message']}")
    print()
    
    # Тест 3: Попытка добавить дубликат
    print("3. 🔄 Попытка добавить дубликат:")
    result = channel_manager.add_channel(
        name="Тестовый канал",
        username="@test_channel",
        channel_id="UCtest123456789"
    )
    if result['success']:
        print(f"   ❌ Дубликат был добавлен (не должно было произойти)")
    else:
        print(f"   ✅ {result['message']}")
    print()
    
    # Тест 4: Получение канала по индексу
    print("4. 🔍 Получение канала по индексу:")
    test_channel = channel_manager.get_channel_by_index(0)
    if test_channel:
        print(f"   ✅ Канал 0: {test_channel['name']}")
    else:
        print("   ❌ Канал не найден")
    print()
    
    # Тест 5: Поиск канала по имени
    print("5. 🔍 Поиск канала по имени:")
    found_channel = channel_manager.find_channel_by_name("Говорилки софтом")
    if found_channel:
        print(f"   ✅ Найден: {found_channel['name']}")
    else:
        print("   ❌ Канал не найден")
    print()
    
    # Тест 6: Удаление тестового канала
    print("6. ➖ Удаление тестового канала:")
    # Найдем индекс тестового канала
    test_index = -1
    for i, channel in enumerate(channel_manager.get_channels()):
        if channel['name'] == "Тестовый канал":
            test_index = i
            break
    
    if test_index >= 0:
        result = channel_manager.remove_channel(test_index)
        if result['success']:
            print(f"   ✅ {result['message']}")
        else:
            print(f"   ❌ {result['message']}")
    else:
        print("   ❌ Тестовый канал не найден для удаления")
    print()
    
    # Тест 7: Финальное состояние
    print("7. 📊 Финальное состояние каналов:")
    final_channels = channel_manager.get_channels()
    print(f"   Всего каналов: {len(final_channels)}")
    for i, channel in enumerate(final_channels, 1):
        print(f"   {i}. {channel['name']} (ID: {channel.get('channel_id', 'НЕТ')})")
    print()
    
    # Тест 8: Проверка файла конфигурации
    print("8. 📁 Проверка файла конфигурации:")
    try:
        with open('channels_config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            print(f"   ✅ Файл конфигурации загружен")
            print(f"   📅 Последнее обновление: {config_data.get('last_updated', 'НЕТ')}")
            print(f"   📺 Каналов в файле: {len(config_data.get('channels', []))}")
    except Exception as e:
        print(f"   ❌ Ошибка при чтении файла: {e}")
    
    print()
    print("🎯 Тестирование Channel Manager завершено!")

if __name__ == "__main__":
    test_channel_manager()
