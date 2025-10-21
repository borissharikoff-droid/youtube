import sys
import os
sys.path.append('C:/Users/fillo/OneDrive/Рабочий стол/dek2/youtube')
os.chdir('C:/Users/fillo/OneDrive/Рабочий стол/dek2/youtube')

from channel_manager import channel_manager

print("🔍 Тестирование Channel Manager...")
print("=" * 50)

# Получение текущих каналов
channels = channel_manager.get_channels()
print(f"Найдено каналов: {len(channels)}")
for i, channel in enumerate(channels, 1):
    print(f"{i}. {channel['name']} (ID: {channel.get('channel_id', 'НЕТ')})")

print("\n✅ Тест завершен!")
