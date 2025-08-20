import json
import time
from datetime import datetime, timedelta
import os
import config

class RequestTracker:
    def __init__(self):
        self.data_file = "request_data.json"
        self.load_data()
    
    def load_data(self):
        """Загружает данные о запросах из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            else:
                self.data = {
                    'users': {},
                    'api_quota': {
                        'used': 0,
                        'reset_time': int(time.time()) + 86400  # Сброс через 24 часа
                    },
                    'last_reset': int(time.time())
                }
        except Exception as e:
            print(f"Ошибка загрузки данных запросов: {e}")
            self.data = {
                'users': {},
                'api_quota': {
                    'used': 0,
                    'reset_time': int(time.time()) + 86400
                },
                'last_reset': int(time.time())
            }
    
    def save_data(self):
        """Сохраняет данные о запросах в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения данных запросов: {e}")
    
    def reset_daily_quota(self):
        """Сбрасывает дневную квоту API"""
        current_time = int(time.time())
        if current_time >= self.data['api_quota']['reset_time']:
            self.data['api_quota']['used'] = 0
            self.data['api_quota']['reset_time'] = current_time + 86400
            self.data['last_reset'] = current_time
            self.save_data()
    
    def can_make_request(self, user_id):
        """Проверяет, может ли пользователь сделать запрос"""
        self.reset_daily_quota()
        
        user_id_str = str(user_id)
        current_time = int(time.time())
        
        # Инициализируем данные пользователя, если их нет
        if user_id_str not in self.data['users']:
            self.data['users'][user_id_str] = {
                'requests_today': 0,
                'last_request': 0,
                'daily_reset': current_time
            }
        
        user_data = self.data['users'][user_id_str]
        
        # Сбрасываем счетчик запросов, если прошел день
        if current_time - user_data['daily_reset'] >= 86400:
            user_data['requests_today'] = 0
            user_data['daily_reset'] = current_time
        
        # Проверяем лимит запросов в день
        if user_data['requests_today'] >= config.DAILY_REQUEST_LIMIT:
            return False, f"Достигнут лимит запросов ({config.DAILY_REQUEST_LIMIT}/день). Попробуйте завтра."
        
        # Проверяем кулдаун между запросами
        if current_time - user_data['last_request'] < config.REQUEST_COOLDOWN:
            remaining_time = config.REQUEST_COOLDOWN - (current_time - user_data['last_request'])
            minutes = remaining_time // 60
            seconds = remaining_time % 60
            return False, f"Подождите {minutes}:{seconds:02d} перед следующим запросом."
        
        return True, "OK"
    
    def record_request(self, user_id, request_type="general"):
        """Записывает запрос пользователя"""
        user_id_str = str(user_id)
        current_time = int(time.time())
        
        # Обновляем данные пользователя
        if user_id_str not in self.data['users']:
            self.data['users'][user_id_str] = {
                'requests_today': 0,
                'last_request': 0,
                'daily_reset': current_time
            }
        
        self.data['users'][user_id_str]['requests_today'] += 1
        self.data['users'][user_id_str]['last_request'] = current_time
        
        # Обновляем квоту API
        quota_cost = config.API_QUOTA_PER_REQUEST.get(request_type, 1)
        self.data['api_quota']['used'] += quota_cost
        
        self.save_data()
    
    def get_user_stats(self, user_id):
        """Получает статистику пользователя"""
        user_id_str = str(user_id)
        current_time = int(time.time())
        
        if user_id_str not in self.data['users']:
            return {
                'requests_today': 0,
                'requests_limit': config.DAILY_REQUEST_LIMIT,
                'remaining_requests': config.DAILY_REQUEST_LIMIT,
                'api_quota_used': self.data['api_quota']['used'],
                'api_quota_limit': config.API_QUOTA_LIMIT
            }
        
        user_data = self.data['users'][user_id_str]
        
        # Сбрасываем счетчик, если прошел день
        if current_time - user_data['daily_reset'] >= 86400:
            user_data['requests_today'] = 0
            user_data['daily_reset'] = current_time
            self.save_data()
        
        return {
            'requests_today': user_data['requests_today'],
            'requests_limit': config.DAILY_REQUEST_LIMIT,
            'remaining_requests': config.DAILY_REQUEST_LIMIT - user_data['requests_today'],
            'api_quota_used': self.data['api_quota']['used'],
            'api_quota_limit': config.API_QUOTA_LIMIT
        }
    
    def get_remaining_quota(self):
        """Получает оставшуюся квоту API"""
        self.reset_daily_quota()
        return config.API_QUOTA_LIMIT - self.data['api_quota']['used']
    
    def is_quota_exceeded(self):
        """Проверяет, превышена ли квота API"""
        return self.data['api_quota']['used'] >= config.API_QUOTA_LIMIT
