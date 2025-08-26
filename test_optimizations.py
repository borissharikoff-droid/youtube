#!/usr/bin/env python3
"""
Тестирование оптимизаций YouTube API
"""

import asyncio
import time
from datetime import datetime
from youtube_stats import YouTubeStats
from youtube_stats_optimized import OptimizedYouTubeStats
import config

def test_performance_comparison():
    """Сравнение производительности старой и новой версий"""
    print("🚀 Тестирование оптимизаций YouTube API")
    print("=" * 50)
    
    # Тестируем старую версию
    print("\n📊 Тестирование старой версии...")
    old_stats = YouTubeStats()
    
    start_time = time.time()
    try:
        old_summary = old_stats.get_summary_stats()
        old_detailed = old_stats.get_detailed_channel_stats()
        old_today_videos = old_stats.get_today_video_stats()
        old_time = time.time() - start_time
        
        print(f"✅ Старая версия выполнена за: {old_time:.2f} секунд")
        print(f"   Сегодня: {old_summary['today']['views']:,} просмотров")
        print(f"   Каналов обработано: {len(old_detailed['today'])}")
        
    except Exception as e:
        print(f"❌ Ошибка в старой версии: {e}")
        old_time = float('inf')
    
    # Тестируем новую версию
    print("\n🚀 Тестирование оптимизированной версии...")
    new_stats = OptimizedYouTubeStats()
    
    start_time = time.time()
    try:
        new_summary = new_stats.get_summary_stats()
        new_detailed = new_stats.get_detailed_channel_stats()
        new_today_videos = new_stats.get_today_video_stats()
        new_time = time.time() - start_time
        
        print(f"✅ Новая версия выполнена за: {new_time:.2f} секунд")
        print(f"   Сегодня: {new_summary['today']['views']:,} просмотров")
        print(f"   Каналов обработано: {len(new_detailed['today'])}")
        
        # Анализ улучшений
        if old_time != float('inf'):
            improvement = ((old_time - new_time) / old_time) * 100
            print(f"\n📈 Улучшение производительности: {improvement:.1f}%")
            print(f"💡 Экономия времени: {old_time - new_time:.2f} секунд")
        
    except Exception as e:
        print(f"❌ Ошибка в новой версии: {e}")

def test_batch_requests():
    """Тестирование batch запросов"""
    print("\n🔗 Тестирование batch запросов каналов...")
    
    new_stats = OptimizedYouTubeStats()
    channel_ids = [channel['channel_id'] for channel in config.CHANNELS]
    
    start_time = time.time()
    batch_results = new_stats.get_batch_channel_stats(channel_ids)
    batch_time = time.time() - start_time
    
    successful_channels = sum(1 for result in batch_results.values() if result is not None)
    
    print(f"✅ Batch запрос выполнен за: {batch_time:.2f} секунд")
    print(f"   Каналов успешно обработано: {successful_channels}/{len(channel_ids)}")
    
    # Показываем результаты
    for channel_id, stats in batch_results.items():
        channel_name = next((c['name'] for c in config.CHANNELS if c['channel_id'] == channel_id), 'Unknown')
        if stats:
            print(f"   📺 {channel_name}: {stats['total_views']:,} просмотров, {stats['subscribers']:,} подписчиков")
        else:
            print(f"   ❌ {channel_name}: ошибка получения данных")

def test_caching():
    """Тестирование системы кэширования"""
    print("\n💾 Тестирование кэширования...")
    
    new_stats = OptimizedYouTubeStats()
    
    # Первый запрос (без кэша)
    print("   Первый запрос (заполнение кэша)...")
    start_time = time.time()
    first_result = new_stats.get_summary_stats()
    first_time = time.time() - start_time
    
    # Второй запрос (с кэшем)
    print("   Второй запрос (из кэша)...")
    start_time = time.time()
    second_result = new_stats.get_summary_stats()
    second_time = time.time() - start_time
    
    cache_speedup = ((first_time - second_time) / first_time) * 100 if first_time > 0 else 0
    
    print(f"✅ Первый запрос: {first_time:.2f} сек")
    print(f"✅ Второй запрос (кэш): {second_time:.2f} сек")
    print(f"🚀 Ускорение от кэша: {cache_speedup:.1f}%")
    
    # Проверяем согласованность данных
    if first_result['today']['views'] == second_result['today']['views']:
        print("✅ Данные из кэша согласованы с оригинальными")
    else:
        print("⚠️ Расхождение в данных кэша")

async def test_async_performance():
    """Тестирование асинхронной производительности"""
    print("\n⚡ Тестирование асинхронной производительности...")
    
    new_stats = OptimizedYouTubeStats()
    
    start_time = time.time()
    result = await new_stats.get_optimized_summary_stats()
    async_time = time.time() - start_time
    
    print(f"✅ Асинхронный запрос выполнен за: {async_time:.2f} секунд")
    print(f"   Обработано каналов: {len(result['detailed']['today'])}")
    print(f"   Общие просмотры за сегодня: {result['summary']['today']['views']:,}")

def show_optimization_summary():
    """Показывает сводку по оптимизациям"""
    print("\n📋 Реализованные оптимизации:")
    print("=" * 50)
    
    optimizations = [
        "✅ Batch запросы для каналов (экономия API квоты)",
        "✅ Умное кэширование с разными TTL:",
        "   • Статистика каналов: 1 час",
        "   • Видео данные: 15 минут", 
        "   • Комментарии: 30 минут",
        "✅ Инкрементальные обновления видео",
        "✅ Параллельные async запросы",
        "✅ Оптимизация получения комментариев",
        "✅ Совместимость со старым API"
    ]
    
    for opt in optimizations:
        print(f"  {opt}")
    
    print(f"\n💡 Ожидаемые улучшения:")
    print(f"  • Снижение использования API квоты на 60-80%")
    print(f"  • Ускорение запросов в 2-5 раз")
    print(f"  • Лучшая отзывчивость бота")
    print(f"  • Более стабильная работа при высокой нагрузке")

def main():
    """Главная функция тестирования"""
    show_optimization_summary()
    
    # Тестируем производительность
    test_performance_comparison()
    
    # Тестируем batch запросы
    test_batch_requests()
    
    # Тестируем кэширование
    test_caching()
    
    # Тестируем async (если поддерживается)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_async_performance())
        loop.close()
    except Exception as e:
        print(f"⚠️ Async тестирование пропущено: {e}")
    
    print(f"\n🎉 Тестирование завершено!")
    print(f"📊 Рекомендация: Переключитесь на OptimizedYouTubeStats для лучшей производительности")

if __name__ == "__main__":
    main()
