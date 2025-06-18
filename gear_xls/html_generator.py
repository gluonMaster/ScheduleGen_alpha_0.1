#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для генерации HTML-версии расписания с интерактивными возможностями
и автоматическим подбором контрастного цвета текста.
ОБНОВЛЕН: Логика работы с цветами вынесена в ColorService.
"""

import os
import logging
import re
import uuid

# Импортируем необходимые модули
from utils import minutes_to_time
from html_styles import get_css_styles
from html_javascript import get_javascript

# Импортируем новый сервис цветов
from services.color_service import ColorService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('html_generator')


def generate_html_schedule(buildings, output_html="schedule.html", output_css="schedule.css", time_interval=5, borderWidth=0.5):
    """
    Генерирует HTML-страницу с интерактивным расписанием.
    
    Args:
        buildings (dict): Структура расписания по зданиям
        output_html (str): Путь для сохранения HTML-файла
        output_css (str): Путь для сохранения CSS-файла (если необходимо)
        time_interval (int): Интервал времени в минутах для отображения в сетке (по умолчанию 5 минут)
        borderWidth (int): Толщина границы ячейки в пикселях (по умолчанию 1 пиксель)
    """
    # Параметры сетки и размеров - точные значения для строгого соответствия
    cellHeight = 15        # высота каждой ячейки (интервал в минутах) в пикселях
    timeColWidth = 80      # ширина столбца времени
    dayCellWidth = 100     # ширина одного подстолбца рабочего дня
    headerHeight = 45      # высота заголовка в пикселях (точное значение)
    days_order = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"]
    
    # Получаем время начала и конца сетки расписания
    # По умолчанию используем 9:00 - 19:45, но если в buildings есть информация, берем из нее
    sample_building = next(iter([b for b in buildings.values() if not isinstance(b, str)]), {})
    grid_start = sample_building.get('_grid_start', 9 * 60)  # 09:00 в минутах
    grid_end = sample_building.get('_grid_end', 19 * 60 + 45)  # 19:45 в минутах
    
    num_rows = ((grid_end - grid_start) // time_interval) + 1
    
    logger.info(f"Генерация HTML-расписания в файл: {output_html}")
    logger.info(f"Временной интервал: {time_interval} мин, время: {minutes_to_time(grid_start)}-{minutes_to_time(grid_end)}")
    logger.info(f"Параметры сетки: cellHeight={cellHeight}px, headerHeight={headerHeight}px, borderWidth={borderWidth}px")

    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang='ru'>")
    html_parts.append("<head>")
    html_parts.append('  <meta charset="UTF-8">')
    html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'  <link rel="stylesheet" type="text/css" href="{output_css}">')
    html_parts.append("  <title>Расписание занятий</title>")
    
    # Встроенные стили
    html_parts.append(get_css_styles(cellHeight, dayCellWidth, timeColWidth, borderWidth))
    
    # Встроенный JavaScript
    html_parts.append(get_javascript(cellHeight, dayCellWidth, headerHeight, days_order, time_interval, borderWidth))
    
    html_parts.append("</head>")
    html_parts.append("<body>")
    
    # Фиксированный блок кнопок для скрытия/показа дней и сохранения результата
    html_parts.append('<div class="sticky-buttons">')
    for day in days_order:
         html_parts.append(f'<button class="toggle-day-button" onclick="toggleDay(this, \'{day}\')">+/- {day}</button>')
    html_parts.append('<button id="saveIntermediate">Сохранить промежуточный результат</button>')
    html_parts.append('<button id="saveSchedule">Сохранить финальную версию</button>')
    html_parts.append('<button id="exportToExcel">Экспорт в Excel</button>')
    
    # Добавляем скрытое поле с CSRF-токеном для безопасной отправки формы
    csrf_token = str(uuid.uuid4())
    html_parts.append(f'<input type="hidden" id="csrf_token" value="{csrf_token}">')
    
    html_parts.append("</div>")
    html_parts.append("<h1>Расписание занятий</h1>")
    
    # Для каждого здания генерируем таблицу-сетку и div-блоки активностей
    for building, data in buildings.items():
        # Пропускаем служебные ключи
        if building.startswith("_"):
            continue
            
        totalCols = 0
        for day in days_order:
            totalCols += data.get('_max_cols', {}).get(day, 1)
        containerWidth = timeColWidth + totalCols * dayCellWidth
        
        html_parts.append(f"<h2>Здание: {building}</h2>")
        html_parts.append(f'<div class="schedule-container" style="width:{containerWidth}px;" data-building="{building}">')
        
        # Генерация таблицы-сетки
        html_parts.append(generate_schedule_table(data, days_order, timeColWidth, num_rows, grid_start, time_interval))
        
        # Наложим div-блоки активностей с корректным позиционированием
        html_parts.append(generate_activity_blocks(data, days_order, dayCellWidth, cellHeight, 
                                                 headerHeight, timeColWidth, grid_start, time_interval, borderWidth))
        
        html_parts.append("</div>")  # конец schedule-container для здания
    
    html_parts.append("</body>")
    html_parts.append("</html>")
    
    # Создаем директорию для HTML файла, если она не существует
    os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
    
    # Записываем HTML-файл
    with open(output_html, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))
    logger.info(f"HTML расписание записано в файл: {output_html}")


def generate_schedule_table(data, days_order, timeColWidth, num_rows, grid_start, time_interval):
    """
    Генерирует HTML таблицу-сетку расписания.
    
    Args:
        data (dict): Данные расписания для конкретного здания
        days_order (list): Порядок дней недели
        timeColWidth (int): Ширина колонки времени
        num_rows (int): Количество строк в таблице
        grid_start (int): Начальное время сетки в минутах
        time_interval (int): Интервал времени в минутах
        
    Returns:
        str: HTML-код таблицы расписания
    """
    html_table = []
    
    html_table.append('<table class="schedule-grid">')
    html_table.append("<thead>")
    html_table.append("<tr>")
    html_table.append('<th class="time-cell">Время</th>')
    
    for day in days_order:
        varCols = data.get('_max_cols', {}).get(day, 1)
        for col in range(varCols):
            # Вычисляем название кабинета, если оно есть
            cabinet = ""
            if day in data.get('_rooms', {}) and len(data['_rooms'][day]) > col:
                cabinet = data['_rooms'][day][col]
            html_table.append(f'<th class="day-{day}">{day}<br>{cabinet}</th>')
    
    html_table.append("</tr>")
    html_table.append("</thead>")
    html_table.append("<tbody>")
    
    for row in range(num_rows):
        html_table.append("<tr>")
        current_time = minutes_to_time(grid_start + row * time_interval)
        
        # Добавляем метку времени только для интервалов, кратных 15 минутам
        time_step = 15 // time_interval  # Вычисляем шаг для меток 15 минут
        display_time = current_time if row % time_step == 0 else ""
        
        html_table.append(f'<td class="time-cell" data-row="{row}" data-col="time">{display_time}</td>')
        
        for day in days_order:
            varCols = data.get('_max_cols', {}).get(day, 1)
            for col in range(varCols):
                html_table.append(f'<td class="day-{day}" data-row="{row}" data-col="{col}"></td>')
        html_table.append("</tr>")
    html_table.append("</tbody>")
    html_table.append("</table>")
    
    return "\n".join(html_table)


def generate_activity_blocks(data, days_order, dayCellWidth, cellHeight, headerHeight, 
                            timeColWidth, grid_start, time_interval, borderWidth):
    """
    Генерирует HTML-код для блоков активностей (занятий) с корректными координатами,
    учитывая толщину границ ячеек таблицы и добавляя контрастный цвет текста.
    ОБНОВЛЕНО: Использует ColorService для работы с цветами.
    
    Args:
        data (dict): Данные расписания для конкретного здания
        days_order (list): Порядок дней недели
        dayCellWidth (int): Ширина ячейки дня
        cellHeight (int): Высота ячейки
        headerHeight (float): Высота заголовка
        timeColWidth (int): Ширина колонки времени
        grid_start (int): Начальное время сетки в минутах
        time_interval (int): Интервал времени в минутах
        borderWidth (int): Толщина границы ячейки
        
    Returns:
        str: HTML-код блоков активностей
    """
    html_blocks = []
    
    for day in days_order:
        dayIndex = days_order.index(day)
        prevWidth = sum(data.get('_max_cols', {}).get(d, 1) for d in days_order[:dayIndex]) * dayCellWidth
        for interval in data.get(day, []):
            col = interval['col']
            
            # Получаем время начала и конца занятия в минутах от начала суток
            start_time = interval['start']
            end_time = interval['end']
            
            # Рассчитываем количество кванторов (5-минутных промежутков) с начала расписания (grid_start)
            start_quants = (start_time - grid_start) // time_interval
            end_quants = (end_time - grid_start) // time_interval
            
            # Рассчитываем точную позицию и размер блока на сетке с учетом толщины границ
            # Учитываем количество границ (количество строк до начала блока)
            # Верхняя граница блока = headerHeight + (start_quants * cellHeight) + (start_quants * borderWidth)
            top = headerHeight + (start_quants * cellHeight) + (start_quants * borderWidth)
            
            # Высота блока = количество кванторов * высота ячейки + (количество внутренних границ * толщина границы)
            # Внутренних границ на 1 меньше, чем кванторов
            quant_count = end_quants - start_quants
            internal_borders = max(0, quant_count - 1)
            height = (quant_count * cellHeight) + (internal_borders * borderWidth * 0.5)
            
            # Позиция по горизонтали
            left = timeColWidth + prevWidth + (col * dayCellWidth)
            
            # Получаем цвет фона и определяем контрастный цвет текста
            bg_color = interval.get('color', '#FFFBD3')  # Желтый по умолчанию
            
            # ИСПОЛЬЗУЕМ ColorService для определения контрастного цвета текста
            text_color = ColorService.get_contrast_text_color(bg_color)
            
            # Текстовая тень в зависимости от цвета текста (для улучшения читаемости)
            text_shadow = "0 0 1px rgba(0, 0, 0, 0.7)" if text_color == "#FFFFFF" else "0 0 1px rgba(255, 255, 255, 0.5)"
            
            # Проверка правильности расчетов и добавление отладочной информации
            logger.debug(f"Занятие {interval['subject']}: время {minutes_to_time(start_time)}-{minutes_to_time(end_time)}")
            logger.debug(f"  Кванторы: {start_quants}-{end_quants}, координаты: top={top}px, height={height}px")
            logger.debug(f"  Цвет фона: {bg_color}, цвет текста: {text_color}")
            
            # Формируем блок активности с контрастным цветом текста
            html_blocks.append(
                f"<div class='activity-block activity-day-{day}' data-day='{day}' data-col-index='{col}' "
                f"data-building='{interval.get('building', '')}' "
                f"style='top:{top}px; left:{left}px; width:{dayCellWidth}px; height:{height}px; "
                f"background-color:{bg_color}; color:{text_color}; text-shadow:{text_shadow};'>"
                f"<strong>{interval['subject'] or 'Не указано'}</strong><br>"
                f"{interval['teacher'] or ''}<br>"
                f"{interval['students'] or ''}<br>"
                f"{interval['room_display'] or ''}<br>"
                f"{minutes_to_time(interval['start'])}-{minutes_to_time(interval['end'])}"
                f"</div>"
            )
    
    return "\n".join(html_blocks)


# ========================================
# ФУНКЦИИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# (удалены - теперь используют ColorService)
# ========================================

# ФУНКЦИЯ УДАЛЕНА: is_light_color() - теперь ColorService.is_light_color()
# ФУНКЦИЯ УДАЛЕНА: get_contrast_text_color() - теперь ColorService.get_contrast_text_color()

# Обертки для обратной совместимости с предупреждениями
def is_light_color(hex_color):
    """
    DEPRECATED: Используйте ColorService.is_light_color()
    
    Args:
        hex_color (str): Цвет в формате HEX
        
    Returns:
        bool: True если цвет светлый
    """
    logger.warning("DEPRECATED: is_light_color() устарел, используйте ColorService.is_light_color()")
    return ColorService.is_light_color(hex_color)


def get_contrast_text_color(hex_color):
    """
    DEPRECATED: Используйте ColorService.get_contrast_text_color()
    
    Args:
        hex_color (str): Цвет фона в формате HEX
        
    Returns:
        str: Контрастный цвет текста
    """
    logger.warning("DEPRECATED: get_contrast_text_color() устарел, используйте ColorService.get_contrast_text_color()")
    return ColorService.get_contrast_text_color(hex_color)


# ========================================
# ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ
# ========================================

def validate_html_generation_params(buildings, time_interval, borderWidth):
    """
    Валидирует параметры для генерации HTML.
    
    Args:
        buildings (dict): Структура расписания
        time_interval (int): Интервал времени
        borderWidth (float): Толщина границ
        
    Returns:
        bool: True если параметры валидны
    """
    if not buildings or not isinstance(buildings, dict):
        logger.error("Некорректная структура buildings")
        return False
        
    if not isinstance(time_interval, int) or time_interval <= 0:
        logger.error(f"Некорректный time_interval: {time_interval}")
        return False
        
    if not isinstance(borderWidth, (int, float)) or borderWidth < 0:
        logger.error(f"Некорректный borderWidth: {borderWidth}")
        return False
        
    return True


def get_html_generator_info():
    """
    Возвращает информацию о HTML генераторе.
    
    Returns:
        dict: Словарь с метаинформацией
    """
    return {
        'version': '2.0.0',  # Увеличена версия после рефакторинга
        'color_service_integration': True,
        'features': [
            'interactive_schedule',
            'drag_and_drop',
            'color_contrast_detection',
            'responsive_design',
            'excel_export'
        ],
        'color_service_version': ColorService.get_service_info()['version'],
        'refactored': True
    }


if __name__ == "__main__":
    # Тест функциональности при прямом запуске
    print("=== HTML Generator Info ===")
    info = get_html_generator_info()
    for key, value in info.items():
        print(f"{key}: {value}")
    
    print("\n=== ColorService Integration Test ===")
    test_colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFFFF', '#000000']
    for color in test_colors:
        is_light = ColorService.is_light_color(color)
        contrast = ColorService.get_contrast_text_color(color)
        print(f"Цвет: {color} → Светлый: {is_light}, Контрастный текст: {contrast}")