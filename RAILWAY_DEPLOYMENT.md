# 🚂 Railway Deployment Guide

## ✅ Готовность к Railway

Код **полностью адаптирован** для развертывания на Railway с поддержкой:

- ✅ **Автоматическое определение среды** (локальная/Railway)
- ✅ **Правильные пути к БД** для файловой системы Railway
- ✅ **Environment variables** поддержка
- ✅ **Persistent storage** для базы данных
- ✅ **Error handling** и restart policies
- ✅ **Logging** оптимизация для cloud

## 📋 Подготовка к деплою

### 1. **Подготовка репозитория**
```bash
# Убедитесь что все файлы в git
git add .
git commit -m "Railway deployment ready"
git push origin main
```

### 2. **Необходимые файлы**
```
📦 Готовые конфигурации:
├── 🚂 railway.json          # Railway конфигурация
├── 📦 requirements.txt      # Зависимости Python
├── ⚙️ config_railway.py     # Конфигурация для Railway
├── 🗂️ Procfile             # Process definition
├── 🐍 runtime.txt           # Python версия
└── 📄 env.example          # Пример переменных
```

## 🔧 Настройка в Railway

### 1. **Создание проекта**
1. Заходим на [railway.app](https://railway.app)
2. Нажимаем **"New Project"**
3. Выбираем **"Deploy from GitHub repo"**
4. Выбираем ваш репозиторий

### 2. **Environment Variables**
Добавляем в Railway Dashboard → Variables:

```bash
# Обязательные переменные
TELEGRAM_TOKEN=ваш_telegram_bot_token
YOUTUBE_API_KEY=ваш_youtube_api_key  
ADMIN_ID=ваш_telegram_user_id

# Опциональные (используются defaults)
DATABASE_PATH=/app/data/youtube_tracker.db
PYTHONUNBUFFERED=1
```

### 3. **Railway автоматически установит**
```bash
RAILWAY_STATIC_URL=ваш_домен.railway.app
PORT=автоматически
```

## 🗄️ База данных на Railway

### **Persistent Storage**
Railway автоматически предоставляет:
- ✅ **Постоянное хранилище** в `/app/data/`
- ✅ **Автоматические бэкапы** файлов
- ✅ **Restart-safe storage** (данные сохраняются)

### **Путь к БД**
```python
# Автоматически выбирается правильный путь:
# Локально: youtube_tracker.db
# Railway: /app/data/youtube_tracker.db
```

### **Миграции**
- ✅ Автоматически выполняются при старте
- ✅ Создание таблиц и индексов
- ✅ Версионирование схемы

## 🚀 Процесс деплоя

### **1. Автоматический деплой**
1. Railway подключается к GitHub репозиторию
2. Автоматически деплоит при push в main
3. Использует `railway.json` конфигурацию

### **2. Build процесс**
```bash
1. Railway клонирует репозиторий
2. Устанавливает Python 3.11.7 (из runtime.txt)
3. Устанавливает зависимости (requirements.txt)
4. Запускает bot.py
```

### **3. Мониторинг деплоя**
```bash
# В Railway Dashboard:
- Logs → Build logs
- Logs → Deploy logs  
- Metrics → CPU/Memory usage
```

## 🔍 Debugging на Railway

### **Logs доступ**
```bash
# В Railway Dashboard → Logs
# Или через CLI:
railway logs
```

### **Основные логи бота**
```
2024-XX-XX Bot initialized with database backend
2024-XX-XX Database migrations completed to version 3
2024-XX-XX YouTube API initialized successfully
2024-XX-XX Bot polling started...
```

### **Troubleshooting**
```bash
# Проверка environment variables
railway variables

# Подключение к контейнеру
railway shell

# Проверка БД
railway shell
>>> ls -la /app/data/
>>> file /app/data/youtube_tracker.db
```

## ⚡ Оптимизации для Railway

### **1. Память и производительность**
- ✅ **SQLite БД** вместо внешней БД
- ✅ **Умное кэширование** с TTL
- ✅ **Batch API запросы** 
- ✅ **Автоматическая очистка** старых данных

### **2. Error handling**
- ✅ **Restart on failure** (до 10 раз)
- ✅ **Graceful shutdown** при ошибках
- ✅ **Database recovery** при проблемах
- ✅ **YouTube API fallbacks**

### **3. Logging**
- ✅ **Structured logging** для Railway
- ✅ **Error tracking** с контекстом
- ✅ **Performance metrics**

## 📊 Monitoring и Maintenance

### **Health Checks**
Railway автоматически мониторит:
- ✅ Process alive status
- ✅ Memory usage
- ✅ CPU usage
- ✅ Network connectivity

### **Metrics доступны**
- 📈 Response times
- 💾 Database size
- 🌐 API quota usage
- 👥 Active users

### **Автоматическое обслуживание**
```python
# БД оптимизация раз в день
youtube_stats.cleanup_old_data(days_to_keep=90)
cache.clear_expired()
db_manager.vacuum_database()
```

## 🔄 Updates и CI/CD

### **Автоматические обновления**
```bash
# При push в main branch:
1. Railway автоматически пересобирает
2. Выполняет миграции БД  
3. Перезапускает сервис
4. Zero-downtime deployment
```

### **Rollback capability**
```bash
# В Railway Dashboard:
Deployments → Previous deployment → Rollback
```

## 🎯 Готовность checklist

- ✅ **Railway.json** настроен
- ✅ **Environment variables** готовы
- ✅ **Database path** адаптирован
- ✅ **Auto-migrations** работают
- ✅ **Error handling** улучшен  
- ✅ **Logging** оптимизирован
- ✅ **Performance** улучшен
- ✅ **Restart policies** настроены

## 🚀 Команды для деплоя

### **Option 1: GitHub Integration (рекомендуется)**
1. Push код в GitHub
2. Подключить репозиторий в Railway
3. Настроить environment variables
4. Railway автоматически деплоит

### **Option 2: Railway CLI**
```bash
# Установка CLI
npm install -g @railway/cli

# Логин
railway login

# Деплой
railway up
```

### **Option 3: Manual ZIP Upload**
1. Архивировать папку проекта
2. Upload в Railway Dashboard
3. Настроить переменные

---

## ✅ **РЕЗУЛЬТАТ**

**YouTube Tracker полностью готов к Railway!**

- 🚂 **Railway-native** конфигурация
- 💾 **Persistent database** storage  
- 🔄 **Auto-migrations** и восстановление
- 📊 **Production-ready** monitoring
- ⚡ **Optimized** для cloud deployment

**Деплой займет 2-3 минуты! 🎉**
