#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вспомогательный модуль с набором утилитарных функций, используемых в разных частях программы.
"""

import re
import hashlib
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('utils')

# Глобальный словарь для сопоставления отдельных аббревиатур с объединённым ключом.
COMPOUND_MAPPING = {
    # Например, если обнаружено, что группы с "2a" и "4c" должны иметь единый ключ:
    "2a": "2a+4c",
    "4c": "2a+4c"
}

def create_output_directories():
    """
    Создает директории для выходных файлов, если они не существуют.
    
    Returns:
        dict: Словарь с путями к директориям
    """
    output_dirs = {
        "html": "html_output",
        "pdf": "pdfs"
    }
    
    for dir_name, dir_path in output_dirs.items():
        os.makedirs(dir_path, exist_ok=True)
        
    return output_dirs

def time_to_minutes(time_str):
    """
    Преобразует время в формате 'HH:MM' в количество минут с начала суток.
    
    Args:
        time_str (str): Время в формате 'HH:MM'
        
    Returns:
        int: Количество минут с начала суток
    """
    if not time_str or not isinstance(time_str, str):
        return 0
        
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except (ValueError, AttributeError):
        logger.warning(f"Невозможно преобразовать время '{time_str}' в минуты. Возвращаем 0.")
        return 0

def minutes_to_time(m):
    """
    Преобразует количество минут в строку формата 'HH:MM'.
    
    Args:
        m (int): Количество минут с начала суток
        
    Returns:
        str: Время в формате 'HH:MM'
    """
    if m is None:
        return "00:00"
    return f"{m // 60:02d}:{m % 60:02d}"

def add_minutes(t, mins):
    """
    Прибавляет к времени в формате 'HH:MM' заданное число минут.
    
    Args:
        t (str): Исходное время в формате 'HH:MM'
        mins (int): Добавляемое количество минут
        
    Returns:
        str: Результирующее время в формате 'HH:MM'
    """
    total = time_to_minutes(t) + mins
    return minutes_to_time(total)

def room_sort_key(room_name):
    """
    Функция возвращает ключ сортировки кабинета по этажам и номерам кабинетов.
    В названии кабинета этаж и номер кабинета разделены точкой (например, '1.06').
    
    Порядок сортировки:
    1. Подвальные кабинеты (K.XX)
    2. Кабинеты первого этажа (0.XX)
    3. Кабинеты верхних этажей (1.XX, 2.XX, ...)
    
    Args:
        room_name (str): Название кабинета
        
    Returns:
        tuple: Кортеж для сортировки (номер_этажа, номер_кабинета)
    """
    if not room_name:
        return (float('inf'), '')
        
    # Проверка формата кабинета с точкой
    match = re.match(r'(\w*)\.(\d+)', room_name)
    if match:
        floor_part, room_part = match.groups()
        # Преобразуем floor_part в числовое значение для сортировки
        if floor_part.lower().startswith('k'):
            floor_num = -1  # Подвал всегда первый
        elif floor_part.isdigit():
            floor_num = int(floor_part)  # Числовые этажи в порядке возрастания
        else:
            floor_num = float('inf')  # Неопределенный формат в конец списка
        
        # Преобразуем room_part в число для правильной числовой сортировки
        try:
            room_num = int(room_part)
        except ValueError:
            room_num = 0
            
        return (floor_num, room_num)
    
    # Обработка для нового формата (например, "K2.3")
    match = re.match(r'(\d+)\.(\d+)', room_name)
    if match:
        floor, room = match.groups()
        return (int(floor), int(room))
    
    return (float('inf'), room_name)  # Если формат не соответствует ожидаемому

def get_color(group):
    """
    Возвращает цвет в формате '#RRGGBB' для заданной группы.
    
    Если в названии группы присутствует конструкция с плюсом, 
    то извлекаются все аббревиатуры, сортируются и объединяются в ключ.
    Если же найдена только одна аббревиатура, то проверяется, входит ли она
    в состав уже известного объединённого ключа (COMPOUND_MAPPING).
    
    Args:
        group (str): Название группы
        
    Returns:
        str: Цвет в формате '#RRGGBB'
    """
    if not group:
        return "#CCCCCC"  # Дефолтный серый для пустых групп
    
    group_lower = str(group).lower()

    # Обработка специальных категорий
    special_categories = {
        "schach": "#ff66cc",
        "tanz": "#66ccff",
        "gitarre": "#ffcc66",
        "deutsch": "#66cc66"
    }
    for keyword, base_color in special_categories.items():
        if keyword in group_lower:
            hash_val = int(hashlib.md5(str(group).encode()).hexdigest(), 16)
            offset = (hash_val % 41) - 20  # смещение от -20 до +20
            base = base_color.lstrip('#')
            r = max(0, min(255, int(base[0:2], 16) + offset))
            g = max(0, min(255, int(base[2:4], 16) + offset))
            b = max(0, min(255, int(base[4:6], 16) + offset))
            return '#{:02x}{:02x}{:02x}'.format(r, g, b)

    # Шаблон для поиска аббревиатур
    pattern = r'\b((?:\d{1,2}[abcdeg])|(?:[34]j[abc])|(?:4-5j)|(?:5-6j))\b'
    # Извлекаем все совпадения
    matches = re.findall(pattern, group_lower)
    # Приводим к уникальному набору
    matches = list(set(matches))
    
    if matches:
        # Если в названии явно присутствует '+', или найдено >1 совпадение,
        # формируем составной ключ как объединение всех аббревиатур.
        if '+' in group or len(matches) > 1:
            canonical_key = '+'.join(sorted(matches))
        else:
            canonical_key = matches[0]
            # Если для найденной аббревиатуры определён объединённый ключ – использовать его.
            if canonical_key in COMPOUND_MAPPING:
                canonical_key = COMPOUND_MAPPING[canonical_key]
    else:
        canonical_key = str(group)

    # Генерация цвета на основе MD5-хэша канонического ключа
    hash_str = hashlib.md5(canonical_key.encode()).hexdigest()
    return '#' + hash_str[:6]
