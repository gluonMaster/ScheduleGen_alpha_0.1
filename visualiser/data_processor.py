"""
Модуль обработки данных расписания
Содержит функции для загрузки и обработки данных из Excel-файла
"""

import pandas as pd
import numpy as np
from datetime import datetime


def load_data(excel_file_path):
    """
    Загружает данные расписания из Excel-файла
    
    Args:
        excel_file_path (str): Путь к Excel-файлу с расписанием
        
    Returns:
        pandas.DataFrame: Датафрейм с данными расписания
    """
    # Загружаем данные с листа Schedule
    df = pd.read_excel(excel_file_path, sheet_name='Schedule')
    
    # Проверяем структуру данных
    required_columns = [
        'subject', 'group', 'teacher', 'room', 'building', 
        'day', 'start_time', 'end_time', 'duration'
    ]
    
    # Убедимся, что все необходимые столбцы присутствуют
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"В таблице отсутствует обязательный столбец '{col}'")
    
    # Убедимся, что start_time и end_time имеют правильный формат времени
    if not pd.api.types.is_datetime64_dtype(df['start_time']):
        df['start_time'] = pd.to_datetime(df['start_time'], format='%H:%M', errors='coerce')
    
    if not pd.api.types.is_datetime64_dtype(df['end_time']):
        df['end_time'] = pd.to_datetime(df['end_time'], format='%H:%M', errors='coerce')
    
    # Извлекаем только время (без даты)
    df['start_time'] = df['start_time'].dt.strftime('%H:%M')
    df['end_time'] = df['end_time'].dt.strftime('%H:%M')
    
    return df


def process_schedule_data(df):
    """
    Обрабатывает данные расписания, группируя их по дням недели
    
    Args:
        df (pandas.DataFrame): Датафрейм с данными расписания
        
    Returns:
        tuple: (список дней недели, словарь с расписанием по дням)
    """
    # Порядок дней недели
    day_order = {'Mo': 0, 'Di': 1, 'Mi': 2, 'Do': 3, 'Fr': 4, 'Sa': 5, 'So': 6}
    
    # Получаем уникальные дни недели в правильном порядке
    unique_days = sorted(df['day'].unique(), key=lambda x: day_order.get(x, 99))
    
    # Словарь для хранения расписания по дням
    schedule_by_day = {}
    
    for day in unique_days:
        # Фильтруем занятия для текущего дня
        day_schedule = df[df['day'] == day].copy()
        
        # Преобразуем время в формат для сортировки
        day_schedule['start_time_dt'] = pd.to_datetime(day_schedule['start_time'], format='%H:%M')
        
        # Сортируем по времени начала
        day_schedule = day_schedule.sort_values('start_time_dt')
        
        # Создаем список занятий для текущего дня с нужной информацией
        lessons = []
        for _, row in day_schedule.iterrows():
            # очищаем номер кабинета от символа-здания (первая буква в названии кабинета):
            original_room = row['room']
            if isinstance(original_room, str) and original_room and original_room[0].isalpha():
                cleaned_room = original_room[1:]
            else:
                cleaned_room = original_room

            lesson = {
                'subject':         row['subject'],
                'group':           row['group'],
                'teacher':         row['teacher'],
                'room':            cleaned_room,     # теперь без первого символа
                'building':        row['building'],
                'start_time':      row['start_time'],
                'end_time':        row['end_time'],
                'duration':        row['duration'],
                'start_time_mins': time_to_minutes(row['start_time']),
                'end_time_mins':   time_to_minutes(row['end_time'])
            }
            lessons.append(lesson)
        
        schedule_by_day[day] = lessons
    
    return unique_days, schedule_by_day


def time_to_minutes(time_str):
    """
    Преобразует время в формате ЧЧ:ММ в количество минут от полуночи
    
    Args:
        time_str (str): Время в формате ЧЧ:ММ
        
    Returns:
        int: Количество минут от полуночи
    """
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except (ValueError, AttributeError):
        # В случае ошибки возвращаем 0
        return 0


def minutes_to_time(minutes):
    """
    Преобразует количество минут от полуночи в время в формате ЧЧ:ММ
    
    Args:
        minutes (int): Количество минут от полуночи
        
    Returns:
        str: Время в формате ЧЧ:ММ
    """
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"
