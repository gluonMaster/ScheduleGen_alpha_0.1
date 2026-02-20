#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор HTML блоков активностей для расписания.
Отвечает за создание позиционированных блоков занятий
с правильным расчетом координат и размеров.
"""

import logging
import sys
import os

# Добавляем родительскую директорию в путь для импорта time_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from time_utils import minutes_to_time
# NOTE: ColorService импортируется отложенно для избежания циклических зависимостей

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('html_block_generator')


class HTMLBlockGenerator:
    """
    Генератор HTML блоков активностей.
    
    Отвечает за:
    - Создание позиционированных блоков занятий
    - Расчет координат и размеров блоков
    - Применение контрастных цветов текста
    - Форматирование содержимого блоков
    """
    
    def __init__(self, day_cell_width=100, cell_height=15, header_height=45, 
                 time_col_width=80, time_interval=5, border_width=0.5):
        """
        Инициализация генератора блоков.
        
        Args:
            day_cell_width (int): Ширина ячейки дня в пикселях
            cell_height (int): Высота ячейки в пикселях
            header_height (int): Высота заголовка в пикселях
            time_col_width (int): Ширина колонки времени в пикселях
            time_interval (int): Интервал времени в минутах
            border_width (float): Толщина границ в пикселях
        """
        self.day_cell_width = day_cell_width
        self.cell_height = cell_height
        self.header_height = header_height
        self.time_col_width = time_col_width
        self.time_interval = time_interval
        self.border_width = border_width
        
        logger.debug(f"Инициализирован HTMLBlockGenerator: "
                    f"cell={day_cell_width}x{cell_height}, interval={time_interval}")
    
    def generate_activity_blocks(self, building_data, days_order, grid_start):
        """
        Генерирует HTML-код для всех блоков активностей здания.
        
        Args:
            building_data (dict): Данные расписания для конкретного здания
            days_order (list): Порядок дней недели
            grid_start (int): Начальное время сетки в минутах
            
        Returns:
            str: HTML-код блоков активностей
        """
        html_blocks = []
        
        for day in days_order:
            day_blocks = self._generate_day_blocks(building_data, day, days_order, grid_start)
            html_blocks.extend(day_blocks)
        
        logger.debug(f"Сгенерировано {len(html_blocks)} блоков активностей")
        return "\n".join(html_blocks)
    
    def _generate_day_blocks(self, building_data, day, days_order, grid_start):
        """
        Генерирует блоки для конкретного дня.
        
        Args:
            building_data (dict): Данные здания
            day (str): День недели
            days_order (list): Порядок дней недели
            grid_start (int): Начальное время сетки в минутах
            
        Returns:
            list: Список HTML строк блоков
        """
        day_blocks = []
        day_index = days_order.index(day)
        
        # ИСПРАВЛЕНИЕ: рассчитываем смещение по горизонтали для текущего дня
        # Точно как в оригинальном коде
        prev_width = sum(building_data.get('_max_cols', {}).get(d, 1) 
                        for d in days_order[:day_index]) * self.day_cell_width
        
        # Отладочная информация
        logger.debug(f"День {day}: day_index={day_index}, prev_width={prev_width}")
        logger.debug(f"  _max_cols: {building_data.get('_max_cols', {})}")
        
        # Генерируем блоки для всех занятий в этом дне
        intervals = building_data.get(day, [])
        logger.debug(f"  Занятий в дне {day}: {len(intervals)}")
        
        for interval in intervals:
            block_html = self._generate_single_block(interval, prev_width, grid_start)
            day_blocks.append(block_html)
        
        return day_blocks
    
    def _generate_single_block(self, interval, left_offset, grid_start):
        """
        Генерирует HTML для одного блока активности.
        
        Args:
            interval (dict): Данные занятия
            left_offset (int): Смещение по горизонтали в пикселях
            grid_start (int): Начальное время сетки в минутах
            
        Returns:
            str: HTML код блока
        """
        # Расчет позиции и размера блока
        position = self._calculate_block_position(interval, left_offset, grid_start)
        
        # Получение цветов
        bg_color = interval.get('color', '#FFFBD3')
        
        # Отложенный импорт ColorService для избежания циклических зависимостей
        try:
            from services.color_service import ColorService
            text_color = ColorService.get_contrast_text_color(bg_color)
        except ImportError:
            # Fallback если ColorService недоступен
            text_color = '#000000' if self._is_light_color_fallback(bg_color) else '#FFFFFF'
        
        text_shadow = self._get_text_shadow(text_color)
        
        # Содержимое блока
        content = self._format_block_content(interval)
        
        # ИСПРАВЛЕНИЕ: Убеждаемся что все атрибуты заполнены правильно
        day = interval.get('day', '')
        col_index = interval.get('col', 0)
        building = interval.get('building', '')

        # Отладочная информация для диагностики
        logger.debug(f"Генерация блока: день='{day}', колонка={col_index}, здание='{building}'")

        # Если атрибуты пустые, это ошибка в данных
        if not day:
            logger.warning(f"ВНИМАНИЕ: Пустой атрибут 'day' для блока {interval.get('subject', 'Unknown')}")
        if not building:
            logger.warning(f"ВНИМАНИЕ: Пустой атрибут 'building' для блока {interval.get('subject', 'Unknown')}")

        # Формирование HTML блока с правильными атрибутами
        block_html = (
            f"<div class='activity-block activity-day-{day}' "
            f"data-day='{day}' "
            f"data-col-index='{col_index}' "
            f"data-building='{building}' "
            f"style='top:{position['top']}px; left:{position['left']}px; "
            f"width:{position['width']}px; height:{position['height']}px; "
            f"background-color:{bg_color}; color:{text_color}; text-shadow:{text_shadow};'>"
            f"{content}"
            f"</div>"
        )
        
        logger.debug(f"Создан блок: {interval.get('subject', 'Неизвестно')} "
                    f"({position['left']},{position['top']}) {position['width']}x{position['height']}")
        
        return block_html
    
    def _calculate_block_position(self, interval, left_offset, grid_start):
        """
        Рассчитывает позицию и размер блока на сетке.
        
        Args:
            interval (dict): Данные занятия
            left_offset (int): Смещение по горизонтали
            grid_start (int): Начальное время сетки в минутах
            
        Returns:
            dict: Словарь с координатами и размерами
        """
        start_time = interval['start']
        end_time = interval['end']
        col = interval.get('col', 0)  # Добавляем значение по умолчанию
        
        # Рассчитываем количество кванторов времени
        start_quants = (start_time - grid_start) // self.time_interval
        end_quants = (end_time - grid_start) // self.time_interval
        quant_count = end_quants - start_quants
        
        # Позиция по вертикали с учетом границ
        top = self.header_height + (start_quants * self.cell_height) + (start_quants * self.border_width)
        
        # Высота блока с учетом внутренних границ
        internal_borders = max(0, quant_count - 1)
        height = (quant_count * self.cell_height) + (internal_borders * self.border_width * 0.5)
        
        # ИСПРАВЛЕНИЕ: позиция по горизонтали - точно как в оригинальном коде
        left = self.time_col_width + left_offset + (col * self.day_cell_width)
        
        # Ширина блока
        width = self.day_cell_width
        
        # Отладочная информация
        logger.debug(f"Блок '{interval.get('subject', 'Unknown')}': "
                    f"col={col}, left_offset={left_offset}, left={left}, "
                    f"time_col_width={self.time_col_width}, day_cell_width={self.day_cell_width}")
        
        return {
            'top': top,
            'left': left,
            'width': width,
            'height': height
        }
    
    def _format_block_content(self, interval):
        """
        Форматирует содержимое блока занятия.
        
        Args:
            interval (dict): Данные занятия
            
        Returns:
            str: HTML содержимое блока
        """
        subject = interval.get('subject') or 'Не указано'
        teacher = interval.get('teacher') or ''
        students = interval.get('students') or ''
        room_display = interval.get('room_display') or ''
        start_time = minutes_to_time(interval.get('start', 0))
        end_time = minutes_to_time(interval.get('end', 0))
        
        content_parts = [
            f"<strong>{subject}</strong><br>",
            f"{teacher}<br>" if teacher else "",
            f"{students}<br>" if students else "",
            f"{room_display}<br>" if room_display else "",
            f"{start_time}-{end_time}"
        ]
        
        return "".join(content_parts)
    
    def _get_text_shadow(self, text_color):
        """
        Возвращает подходящую тень для текста.
        
        Args:
            text_color (str): Цвет текста
            
        Returns:
            str: CSS свойство text-shadow
        """
        return ("0 0 1px rgba(0, 0, 0, 0.7)" if text_color == "#FFFFFF" 
                else "0 0 1px rgba(255, 255, 255, 0.5)")
    
    def _is_light_color_fallback(self, hex_color):
        """
        Fallback функция для определения светлоты цвета.
        
        Args:
            hex_color (str): Цвет в формате HEX
            
        Returns:
            bool: True если цвет светлый
        """
        if not hex_color or not hex_color.startswith('#') or len(hex_color) != 7:
            return True
        
        try:
            # Извлекаем RGB компоненты
            r = int(hex_color[1:3], 16) / 255.0
            g = int(hex_color[3:5], 16) / 255.0
            b = int(hex_color[5:7], 16) / 255.0
            
            # Вычисляем яркость
            brightness = 0.299 * r + 0.587 * g + 0.114 * b
            return brightness > 0.55
        except ValueError:
            return True
    
    def validate_interval_data(self, interval):
        """
        Проверяет валидность данных занятия.
        
        Args:
            interval (dict): Данные занятия
            
        Returns:
            bool: True если данные валидны
        """
        required_fields = ['start', 'end', 'col']
        
        for field in required_fields:
            if field not in interval:
                logger.error(f"Отсутствует обязательное поле: {field}")
                return False
        
        start = interval.get('start', 0)
        end = interval.get('end', 0)
        
        if start >= end:
            logger.error(f"Некорректное время: начало ({start}) >= конец ({end})")
            return False
        
        return True
    
    def get_block_statistics(self, building_data, days_order):
        """
        Собирает статистику по блокам занятий.
        
        Args:
            building_data (dict): Данные здания
            days_order (list): Порядок дней недели
            
        Returns:
            dict: Статистика блоков
        """
        total_blocks = 0
        blocks_by_day = {}
        
        for day in days_order:
            day_blocks = len(building_data.get(day, []))
            blocks_by_day[day] = day_blocks
            total_blocks += day_blocks
        
        return {
            'total_blocks': total_blocks,
            'blocks_by_day': blocks_by_day,
            'average_per_day': total_blocks / len(days_order) if days_order else 0
        }
    
    def get_generator_info(self):
        """
        Возвращает информацию о генераторе блоков.
        
        Returns:
            dict: Словарь с метаинформацией
        """
        return {
            'generator': 'HTMLBlockGenerator',
            'version': '1.0.0',
            'day_cell_width': self.day_cell_width,
            'cell_height': self.cell_height,
            'time_interval': self.time_interval,
            'border_width': self.border_width,
            'features': [
                'precise_positioning',
                'contrast_colors',
                'border_compensation',
                'content_formatting'
            ]
        }