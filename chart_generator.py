#!/usr/bin/env python3
"""
Генератор красивых изображений со статистикой YouTube каналов
Создает информативные и визуально привлекательные графики
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np
import seaborn as sns
from datetime import datetime, timedelta
import os
import io
from PIL import Image, ImageDraw, ImageFont
import logging

# Настройка стилей
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

logger = logging.getLogger(__name__)

class YouTubeChartGenerator:
    def __init__(self):
        """Инициализация генератора графиков"""
        self.colors = {
            'primary': '#FF0000',      # YouTube красный
            'secondary': '#282828',    # Темно-серый
            'accent': '#00D4FF',       # Голубой
            'success': '#00FF88',      # Зеленый
            'warning': '#FFB800',      # Оранжевый
            'text': '#FFFFFF',         # Белый
            'text_secondary': '#CCCCCC' # Светло-серый
        }
        
        # Настройка шрифтов
        self.setup_fonts()
        
    def setup_fonts(self):
        """Настройка шрифтов для русского текста"""
        try:
            # Пытаемся использовать системные шрифты
            self.title_font = plt.matplotlib.font_manager.FontProperties(
                family='Arial', size=24, weight='bold'
            )
            self.subtitle_font = plt.matplotlib.font_manager.FontProperties(
                family='Arial', size=16, weight='normal'
            )
            self.label_font = plt.matplotlib.font_manager.FontProperties(
                family='Arial', size=12, weight='normal'
            )
        except:
            # Fallback на стандартные шрифты
            self.title_font = None
            self.subtitle_font = None
            self.label_font = None
    
    def create_summary_chart(self, summary_stats, detailed_stats, channels_info):
        """Создает сводный график статистики"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.patch.set_facecolor('#1a1a1a')
        
        # 1. Столбчатая диаграмма просмотров по каналам
        self._create_views_chart(ax1, detailed_stats)
        
        # 2. Круговая диаграмма лайков
        self._create_likes_pie_chart(ax2, detailed_stats)
        
        # 3. Сравнение периодов
        self._create_periods_comparison(ax3, summary_stats)
        
        # 4. Общая статистика
        self._create_overview_stats(ax4, summary_stats, channels_info)
        
        # Общий заголовок
        fig.suptitle('📊 YouTube Analytics Dashboard', 
                    fontsize=28, color='white', fontweight='bold', y=0.95)
        
        plt.tight_layout()
        return fig
    
    def _create_views_chart(self, ax, detailed_stats):
        """Создает столбчатую диаграмму просмотров"""
        ax.set_facecolor('#2a2a2a')
        
        channels = [ch['channel_name'] for ch in detailed_stats['today']]
        views = [ch['views'] for ch in detailed_stats['today']]
        
        bars = ax.bar(channels, views, color=self.colors['primary'], alpha=0.8, edgecolor='white', linewidth=2)
        
        # Добавляем значения на столбцы
        for bar, value in zip(bars, views):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + max(views)*0.01,
                   f'{value:,}', ha='center', va='bottom', color='white', fontweight='bold')
        
        ax.set_title('👁️ Просмотры за сегодня', color='white', fontsize=16, fontweight='bold')
        ax.set_ylabel('Просмотры', color='white')
        ax.tick_params(colors='white')
        
        # Поворачиваем названия каналов для лучшей читаемости
        plt.setp(ax.get_xticklabels(), rotation=15, ha='right')
    
    def _create_likes_pie_chart(self, ax, detailed_stats):
        """Создает круговую диаграмму лайков"""
        ax.set_facecolor('#2a2a2a')
        
        channels = [ch['channel_name'] for ch in detailed_stats['today']]
        likes = [ch['likes'] for ch in detailed_stats['today']]
        
        # Фильтруем каналы с нулевыми лайками
        non_zero_data = [(ch, lk) for ch, lk in zip(channels, likes) if lk > 0]
        
        if non_zero_data:
            channels_filtered, likes_filtered = zip(*non_zero_data)
            colors = [self.colors['primary'], self.colors['accent'], self.colors['success']][:len(channels_filtered)]
            
            wedges, texts, autotexts = ax.pie(likes_filtered, labels=channels_filtered, 
                                            colors=colors, autopct='%1.1f%%', 
                                            startangle=90, textprops={'color': 'white'})
            
            # Стилизуем текст
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
        else:
            ax.text(0.5, 0.5, 'Нет лайков\nза сегодня', ha='center', va='center', 
                   color='white', fontsize=14, transform=ax.transAxes)
        
        ax.set_title('👍 Распределение лайков', color='white', fontsize=16, fontweight='bold')
    
    def _create_periods_comparison(self, ax, summary_stats):
        """Создает сравнение периодов"""
        ax.set_facecolor('#2a2a2a')
        
        periods = ['Сегодня', 'Вчера', 'Неделя', 'Все время']
        views = [
            summary_stats['today']['views'],
            summary_stats['yesterday']['views'],
            summary_stats['week']['views'],
            summary_stats['all_time']['views']
        ]
        
        # Нормализуем данные для лучшего отображения
        max_views = max(views)
        normalized_views = [v / max_views * 100 if max_views > 0 else 0 for v in views]
        
        bars = ax.bar(periods, normalized_views, 
                     color=[self.colors['primary'], self.colors['accent'], 
                           self.colors['success'], self.colors['warning']],
                     alpha=0.8, edgecolor='white', linewidth=2)
        
        # Добавляем значения
        for bar, value in zip(bars, views):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{value:,}', ha='center', va='bottom', color='white', fontweight='bold')
        
        ax.set_title('📈 Сравнение периодов', color='white', fontsize=16, fontweight='bold')
        ax.set_ylabel('Просмотры (нормализовано)', color='white')
        ax.tick_params(colors='white')
    
    def _create_overview_stats(self, ax, summary_stats, channels_info):
        """Создает общую статистику"""
        ax.set_facecolor('#2a2a2a')
        ax.axis('off')
        
        # Создаем текстовую статистику
        stats_text = f"""
📊 ОБЩАЯ СТАТИСТИКА

🎬 Каналов отслеживается: {len(channels_info)}

📅 СЕГОДНЯ:
   👁️ Просмотры: {summary_stats['today']['views']:,}
   👍 Лайки: {summary_stats['today']['likes']:,}
   💬 Комментарии: {summary_stats['today']['comments']:,}
   🎬 Видео: {summary_stats['today'].get('video_count', 0):,}

📅 ВЧЕРА:
   👁️ Просмотры: {summary_stats['yesterday']['views']:,}
   👍 Лайки: {summary_stats['yesterday']['likes']:,}
   💬 Комментарии: {summary_stats['yesterday']['comments']:,}
   🎬 Видео: {summary_stats['yesterday'].get('video_count', 0):,}

📅 ВСЕ ВРЕМЯ:
   👁️ Просмотры: {summary_stats['all_time']['views']:,}
   👍 Лайки: {summary_stats['all_time']['likes']:,}
   💬 Комментарии: {summary_stats['all_time']['comments']:,}
   👥 Подписчики: {summary_stats['all_time'].get('subscribers', 0):,}
   🎬 Видео: {summary_stats['all_time'].get('videos', 0):,}
        """
        
        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=12,
               verticalalignment='top', color='white', fontfamily='monospace',
               bbox=dict(boxstyle="round,pad=0.5", facecolor='#333333', alpha=0.8))
    
    def create_detailed_channel_chart(self, detailed_stats):
        """Создает детальный график по каналам"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        fig.patch.set_facecolor('#1a1a1a')
        
        # 1. Сравнение каналов по метрикам
        self._create_metrics_comparison(ax1, detailed_stats)
        
        # 2. Тренды по каналам
        self._create_channel_trends(ax2, detailed_stats)
        
        fig.suptitle('📺 Детальная статистика по каналам', 
                    fontsize=24, color='white', fontweight='bold')
        
        plt.tight_layout()
        return fig
    
    def _create_metrics_comparison(self, ax, detailed_stats):
        """Создает сравнение метрик по каналам"""
        ax.set_facecolor('#2a2a2a')
        
        channels = [ch['channel_name'] for ch in detailed_stats['today']]
        views = [ch['views'] for ch in detailed_stats['today']]
        likes = [ch['likes'] for ch in detailed_stats['today']]
        comments = [ch['comments'] for ch in detailed_stats['today']]
        
        x = np.arange(len(channels))
        width = 0.25
        
        # Нормализуем данные для лучшего отображения
        max_views = max(views) if views else 1
        max_likes = max(likes) if likes else 1
        max_comments = max(comments) if comments else 1
        
        normalized_views = [v / max_views * 100 for v in views]
        normalized_likes = [l / max_likes * 100 for l in likes]
        normalized_comments = [c / max_comments * 100 for c in comments]
        
        bars1 = ax.bar(x - width, normalized_views, width, label='Просмотры', 
                      color=self.colors['primary'], alpha=0.8)
        bars2 = ax.bar(x, normalized_likes, width, label='Лайки', 
                      color=self.colors['accent'], alpha=0.8)
        bars3 = ax.bar(x + width, normalized_comments, width, label='Комментарии', 
                      color=self.colors['success'], alpha=0.8)
        
        ax.set_title('📊 Сравнение метрик по каналам', color='white', fontsize=16, fontweight='bold')
        ax.set_ylabel('Нормализованные значения (%)', color='white')
        ax.set_xticks(x)
        ax.set_xticklabels(channels, rotation=15, ha='right')
        ax.legend()
        ax.tick_params(colors='white')
        
        # Добавляем значения на столбцы
        for bars, values in [(bars1, views), (bars2, likes), (bars3, comments)]:
            for bar, value in zip(bars, values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                       f'{value:,}', ha='center', va='bottom', color='white', fontsize=8)
    
    def _create_channel_trends(self, ax, detailed_stats):
        """Создает тренды по каналам"""
        ax.set_facecolor('#2a2a2a')
        
        # Сравниваем сегодня vs вчера
        today_data = detailed_stats['today']
        yesterday_data = detailed_stats.get('yesterday', [])
        
        channels = [ch['channel_name'] for ch in today_data]
        today_views = [ch['views'] for ch in today_data]
        
        # Находим соответствующие данные за вчера
        yesterday_views = []
        for channel in channels:
            yesterday_channel = next((ch for ch in yesterday_data if ch['channel_name'] == channel), None)
            yesterday_views.append(yesterday_channel['views'] if yesterday_channel else 0)
        
        x = np.arange(len(channels))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, today_views, width, label='Сегодня', 
                      color=self.colors['primary'], alpha=0.8)
        bars2 = ax.bar(x + width/2, yesterday_views, width, label='Вчера', 
                      color=self.colors['accent'], alpha=0.8)
        
        ax.set_title('📈 Тренды просмотров', color='white', fontsize=16, fontweight='bold')
        ax.set_ylabel('Просмотры', color='white')
        ax.set_xticks(x)
        ax.set_xticklabels(channels, rotation=15, ha='right')
        ax.legend()
        ax.tick_params(colors='white')
        
        # Добавляем значения
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + max(today_views + yesterday_views)*0.01,
                       f'{int(height):,}', ha='center', va='bottom', color='white', fontsize=8)
    
    def create_infographic(self, summary_stats, detailed_stats, channels_info):
        """Создает красивую инфографику"""
        fig = plt.figure(figsize=(20, 12))
        fig.patch.set_facecolor('#1a1a1a')
        
        # Создаем сетку
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
        
        # Заголовок
        title_ax = fig.add_subplot(gs[0, :])
        title_ax.axis('off')
        title_ax.text(0.5, 0.5, '📊 YouTube Analytics Dashboard', 
                     ha='center', va='center', fontsize=32, color='white', 
                     fontweight='bold', transform=title_ax.transAxes)
        
        # Основные метрики
        self._create_metric_cards(fig, gs[1, :2], summary_stats)
        
        # График просмотров
        views_ax = fig.add_subplot(gs[1, 2:])
        self._create_views_chart(views_ax, detailed_stats)
        
        # Круговая диаграмма лайков
        likes_ax = fig.add_subplot(gs[2, :2])
        self._create_likes_pie_chart(likes_ax, detailed_stats)
        
        # Список каналов
        channels_ax = fig.add_subplot(gs[2, 2:])
        self._create_channels_list(channels_ax, channels_info)
        
        return fig
    
    def _create_metric_cards(self, fig, gs, summary_stats):
        """Создает карточки с метриками"""
        ax = fig.add_subplot(gs)
        ax.axis('off')
        
        # Создаем карточки метрик
        metrics = [
            ('👁️ Просмотры сегодня', summary_stats['today']['views'], self.colors['primary']),
            ('👍 Лайки сегодня', summary_stats['today']['likes'], self.colors['accent']),
            ('💬 Комментарии сегодня', summary_stats['today']['comments'], self.colors['success']),
            ('🎬 Видео сегодня', summary_stats['today'].get('video_count', 0), self.colors['warning'])
        ]
        
        for i, (title, value, color) in enumerate(metrics):
            x = 0.1 + (i % 2) * 0.4
            y = 0.7 - (i // 2) * 0.4
            
            # Создаем карточку
            card = FancyBboxPatch((x, y), 0.35, 0.25, 
                                boxstyle="round,pad=0.02", 
                                facecolor=color, alpha=0.8,
                                edgecolor='white', linewidth=2)
            ax.add_patch(card)
            
            # Добавляем текст
            ax.text(x + 0.175, y + 0.15, title, ha='center', va='center', 
                   color='white', fontsize=12, fontweight='bold')
            ax.text(x + 0.175, y + 0.05, f'{value:,}', ha='center', va='center', 
                   color='white', fontsize=16, fontweight='bold')
    
    def _create_channels_list(self, ax, channels_info):
        """Создает список каналов"""
        ax.set_facecolor('#2a2a2a')
        ax.axis('off')
        
        ax.set_title('📺 Отслеживаемые каналы', color='white', fontsize=16, fontweight='bold')
        
        channels_text = ""
        for i, channel in enumerate(channels_info, 1):
            channels_text += f"{i}. {channel['name']}\n"
            if channel.get('username'):
                channels_text += f"   @{channel['username']}\n"
            if channel.get('channel_id'):
                channels_text += f"   ID: {channel['channel_id'][:8]}...\n"
            channels_text += "\n"
        
        ax.text(0.05, 0.95, channels_text, transform=ax.transAxes, fontsize=12,
               verticalalignment='top', color='white', fontfamily='monospace')
    
    def save_chart(self, fig, filename, dpi=300):
        """Сохраняет график в файл"""
        try:
            fig.savefig(filename, dpi=dpi, bbox_inches='tight', 
                       facecolor='#1a1a1a', edgecolor='none')
            logger.info(f"График сохранен: {filename}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения графика: {e}")
            return False
    
    def get_chart_bytes(self, fig):
        """Возвращает график как байты для отправки в Telegram"""
        try:
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', dpi=300, bbox_inches='tight',
                       facecolor='#1a1a1a', edgecolor='none')
            buffer.seek(0)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Ошибка создания байтов графика: {e}")
            return None

def create_sample_chart():
    """Создает пример графика для тестирования"""
    generator = YouTubeChartGenerator()
    
    # Примерные данные
    summary_stats = {
        'today': {'views': 648, 'likes': 8, 'comments': 0, 'video_count': 3},
        'yesterday': {'views': 2330, 'likes': 19, 'comments': 0, 'video_count': 4},
        'week': {'views': 2330, 'likes': 19, 'comments': 0, 'video_count': 4},
        'all_time': {'views': 129665, 'likes': 19, 'comments': 0, 'subscribers': 111, 'videos': 31}
    }
    
    detailed_stats = {
        'today': [
            {'channel_name': 'Говорилки софтом', 'views': 338, 'likes': 3, 'comments': 0},
            {'channel_name': 'Премия дарвина', 'views': 3, 'likes': 0, 'comments': 0},
            {'channel_name': 'Милитари', 'views': 307, 'likes': 5, 'comments': 0}
        ],
        'yesterday': [
            {'channel_name': 'Говорилки софтом', 'views': 2018, 'likes': 19, 'comments': 0},
            {'channel_name': 'Премия дарвина', 'views': 312, 'likes': 0, 'comments': 0},
            {'channel_name': 'Милитари', 'views': 0, 'likes': 0, 'comments': 0}
        ]
    }
    
    channels_info = [
        {'name': 'Говорилки софтом', 'channel_id': 'UCAwrVTXIRxk8FDpyr6T_j7A'},
        {'name': 'Премия дарвина', 'channel_id': 'UCru-f82fjfVHWi2COAUR8eQ'},
        {'name': 'Милитари', 'channel_id': 'UC2q4rIDzF9F_oCQkhG2tizw'}
    ]
    
    # Создаем разные типы графиков
    fig1 = generator.create_summary_chart(summary_stats, detailed_stats, channels_info)
    generator.save_chart(fig1, 'youtube_summary_chart.png')
    
    fig2 = generator.create_detailed_channel_chart(detailed_stats)
    generator.save_chart(fig2, 'youtube_detailed_chart.png')
    
    fig3 = generator.create_infographic(summary_stats, detailed_stats, channels_info)
    generator.save_chart(fig3, 'youtube_infographic.png')
    
    print("✅ Графики созданы успешно!")
    print("📁 Файлы:")
    print("   - youtube_summary_chart.png")
    print("   - youtube_detailed_chart.png") 
    print("   - youtube_infographic.png")

if __name__ == "__main__":
    create_sample_chart()
