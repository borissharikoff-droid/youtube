import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
import config

logger = logging.getLogger(__name__)

class ChannelManager:
    """Класс для управления каналами в конфигурации"""
    
    def __init__(self, config_file_path: str = "channels_config.json"):
        self.config_file_path = config_file_path
        self.channels = self._load_channels()
    
    def _load_channels(self) -> List[Dict]:
        """Загружает каналы из файла конфигурации"""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('channels', [])
            else:
                # Если файл не существует, создаем его с текущими каналами из config.py
                channels = config.CHANNELS.copy()
                self._save_channels(channels)
                return channels
        except Exception as e:
            logger.error(f"Ошибка при загрузке каналов: {e}")
            return config.CHANNELS.copy()
    
    def _save_channels(self, channels: List[Dict]) -> bool:
        """Сохраняет каналы в файл конфигурации"""
        try:
            data = {
                'channels': channels,
                'last_updated': str(datetime.now())
            }
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Обновляем глобальную переменную config.CHANNELS
            config.CHANNELS = channels.copy()
            
            logger.info(f"Каналы сохранены: {len(channels)} каналов")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении каналов: {e}")
            return False
    
    def add_channel(self, name: str, username: str = "", channel_id: str = "") -> Dict:
        """Добавляет новый канал"""
        # Проверяем, не существует ли уже такой канал
        for channel in self.channels:
            if (channel.get('name', '').lower() == name.lower() or 
                channel.get('username', '').lower() == username.lower() or
                channel.get('channel_id', '') == channel_id):
                return {
                    'success': False,
                    'message': 'Канал уже существует в списке отслеживания'
                }
        
        new_channel = {
            'name': name,
            'username': username,
            'channel_id': channel_id
        }
        
        self.channels.append(new_channel)
        
        if self._save_channels(self.channels):
            return {
                'success': True,
                'message': f'Канал "{name}" успешно добавлен',
                'channel': new_channel
            }
        else:
            # Откатываем изменения
            self.channels.pop()
            return {
                'success': False,
                'message': 'Ошибка при сохранении конфигурации'
            }
    
    def remove_channel(self, index: int) -> Dict:
        """Удаляет канал по индексу"""
        if 0 <= index < len(self.channels):
            removed_channel = self.channels.pop(index)
            
            if self._save_channels(self.channels):
                return {
                    'success': True,
                    'message': f'Канал "{removed_channel["name"]}" удален',
                    'channel': removed_channel
                }
            else:
                # Откатываем изменения
                self.channels.insert(index, removed_channel)
                return {
                    'success': False,
                    'message': 'Ошибка при сохранении конфигурации'
                }
        else:
            return {
                'success': False,
                'message': 'Неверный индекс канала'
            }
    
    def get_channels(self) -> List[Dict]:
        """Возвращает список всех каналов"""
        return self.channels.copy()
    
    def get_channel_by_index(self, index: int) -> Optional[Dict]:
        """Возвращает канал по индексу"""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None
    
    def update_channel(self, index: int, name: str = None, username: str = None, channel_id: str = None) -> Dict:
        """Обновляет информацию о канале"""
        if 0 <= index < len(self.channels):
            channel = self.channels[index]
            
            if name is not None:
                channel['name'] = name
            if username is not None:
                channel['username'] = username
            if channel_id is not None:
                channel['channel_id'] = channel_id
            
            if self._save_channels(self.channels):
                return {
                    'success': True,
                    'message': f'Канал "{channel["name"]}" обновлен',
                    'channel': channel
                }
            else:
                return {
                    'success': False,
                    'message': 'Ошибка при сохранении конфигурации'
                }
        else:
            return {
                'success': False,
                'message': 'Неверный индекс канала'
            }
    
    def find_channel_by_name(self, name: str) -> Optional[Dict]:
        """Находит канал по имени"""
        for channel in self.channels:
            if channel.get('name', '').lower() == name.lower():
                return channel
        return None
    
    def find_channel_by_username(self, username: str) -> Optional[Dict]:
        """Находит канал по username"""
        clean_username = username.lstrip('@').lower()
        for channel in self.channels:
            channel_username = channel.get('username', '').lstrip('@').lower()
            if channel_username == clean_username:
                return channel
        return None
    
    def reload_channels(self) -> bool:
        """Перезагружает каналы из файла"""
        try:
            self.channels = self._load_channels()
            config.CHANNELS = self.channels.copy()
            return True
        except Exception as e:
            logger.error(f"Ошибка при перезагрузке каналов: {e}")
            return False

# Создаем глобальный экземпляр менеджера каналов
channel_manager = ChannelManager()
