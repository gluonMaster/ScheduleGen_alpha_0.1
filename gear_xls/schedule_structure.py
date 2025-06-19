#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для формирования структуры расписания из исходных данных.
Группирует занятия по зданиям, дням недели и кабинетам,
рассчитывает позиции и размеры блоков для визуализации.
"""

import logging
from utils import time_to_minutes, get_color, room_sort_key

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('schedule_structure')

def build_schedule_structure(activities, time_interval=5):
    """
    На основе словаря activities (ключ – id активности, значение – данные активности)
    формируется структура для генерации расписания по зданиям.

    Возвращаемая структура:
    buildings = {
        'BuildingName': {
            'Mo': [interval, ...],
            'Di': [...],
            ...
            '_max_cols': { 'Mo': N, 'Di': M, ... },
            '_grid': { 'Mo': {(col, row_start): interval, ...}, ... },
            '_rooms': { 'Mo': [room1, room2, ...], ... }
        },
        ...
    }

    Каждый interval – словарь с полями:
      id, start, end (в минутах), teacher, subject, students, room, room_display, color,
      row_start, rowspan, col.
      
    Args:
        activities (dict): Словарь с информацией о занятиях из Excel-парсера
        time_interval (int): Интервал времени в минутах для отображения в сетке (по умолчанию 5 минут)
        
    Returns:
        dict: Структурированное расписание по зданиям
    """
    buildings = {}
    days_order = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"]
    
    # Определяем начало и конец сетки расписания
    grid_start = 9 * 60  # 09:00 в минутах
    grid_end = 19 * 60 + 45  # 19:45 в минутах
    
    logger.info("Начинаем формирование структуры расписания")
    logger.info(f"Интервал времени: {time_interval} минут")
    logger.info(f"Начало сетки: {grid_start//60:02d}:{grid_start%60:02d}, Конец сетки: {grid_end//60:02d}:{grid_end%60:02d}")

    try:
        # Сначала группируем занятия по зданиям и дням недели
        for act_id, details in activities.items():
            building = details['building']
            day = details['day']
            if not building or not day:
                continue

            if building not in buildings:
                buildings[building] = {}

            if day not in buildings[building]:
                buildings[building][day] = []

            # Преобразуем время начала и окончания в минуты
            start = time_to_minutes(details['start_time'])
            end = time_to_minutes(details['end_time'])

            # Проверяем, что время попадает в пределы сетки
            if start < grid_start:
                logger.warning(f"Занятие {details['subject']} для {details['teacher']} начинается раньше начала сетки ({start} < {grid_start})")
            if end > grid_end:
                logger.warning(f"Занятие {details['subject']} для {details['teacher']} заканчивается позже конца сетки ({end} > {grid_end})")

            interval = {
                "id": act_id,
                "start": start,
                "end": end,
                "teacher": details['teacher'],
                "subject": details['subject'],
                "students": details['students'],  # имя группы
                "room": details['room'],
                "room_display": details['room_display'],  # Очищенное название кабинета
                "color": get_color(details.get('students', 'default')),
                # ИСПРАВЛЕНИЕ: Добавляем поля day и building для JavaScript
                "day": day,
                "building": building
            }
            buildings[building][day].append(interval)

        # Для каждого здания определяем количество подстолбцов для каждого дня 
        # на основе уникальных кабинетов
        for building in buildings:
            max_cols = {}
            rooms_by_day = {}

            for day in days_order:
                if day in buildings[building]:
                    intervals = buildings[building][day]

                    # Получаем и сортируем список уникальных кабинетов
                    unique_rooms_list = sorted(
                        {interval['room_display'] for interval in intervals},
                        key=room_sort_key
                    )
                    rooms_by_day[day] = unique_rooms_list

                    # Присваиваем индекс столбца согласно позиции в отсортированном списке кабинетов
                    for interval in intervals:
                        interval['col'] = unique_rooms_list.index(interval['room_display'])

                    max_cols[day] = len(unique_rooms_list)
                else:
                    max_cols[day] = 1
                    rooms_by_day[day] = []

            buildings[building]['_max_cols'] = max_cols
            buildings[building]['_rooms'] = rooms_by_day
            buildings[building]['_grid_start'] = grid_start
            buildings[building]['_grid_end'] = grid_end

            # Вычисляем row_start и rowspan для размещения на сетке
            for day in days_order:
                if day in buildings[building]:
                    for interval in buildings[building][day]:
                        # Вычисляем индекс строки с учетом времени начала занятия
                        # Для точного позиционирования блоков занятий
                        start_time = interval['start']
                        end_time = interval['end']
                        
                        # Рассчитываем количество интервалов с начала сетки
                        row_start = (start_time - grid_start) // time_interval
                        if row_start < 0:
                            row_start = 0
                            
                        # Рассчитываем количество строк для блока занятия
                        row_end = (end_time - grid_start) // time_interval
                        row_span = max(1, row_end - row_start)
                        
                        # Сохраняем вычисленные значения
                        interval['row_start'] = row_start
                        interval['rowspan'] = row_span

            # Формируем сетку для быстрого доступа: grid[day][(col, row_start)] = interval
            grid = {}
            for day in days_order:
                grid[day] = {}
                if day in buildings[building]:
                    for interval in buildings[building][day]:
                        grid[day][(interval['col'], interval['row_start'])] = interval
            buildings[building]['_grid'] = grid

        logger.info(f"Структура расписания сформирована для {len(buildings)} зданий")
        return buildings
    
    except Exception as e:
        logger.error(f"Ошибка при формировании структуры расписания: {e}")
        import traceback
        traceback.print_exc()
        return {}
