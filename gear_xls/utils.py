#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вспомогательный модуль с набором утилитарных функций, используемых в разных частях программы.
ОБНОВЛЕН: Логика работы с цветами вынесена в ColorService.
"""

import re
import os
import logging

# Импортируем новый сервис цветов
from services.color_service import ColorService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('utils')


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


# ========================================
# ФУНКЦИИ ДЛЯ РАБОТЫ СО ВРЕМЕНЕМ
# ========================================

def time_to_minutes(time_str):
    """
    Преобразует время в формате 'HH:MM' в количество минут с начала суток.
    
    Args:
        time_str (str): Время в формате 'HH:MM'
        
    Returns:
        int: Количество минут с начала суток
    """
    if not time_str or not isinstance(time_str, str):
        logger.warning(f"Некорректное время: {time_str}, возвращаем 0")
        return 0
        
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except (ValueError, AttributeError) as e:
        logger.warning(f"Невозможно преобразовать время '{time_str}' в минуты: {e}. Возвращаем 0.")
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


# ========================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С КАБИНЕТАМИ
# ========================================

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


# ========================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ЦВЕТАМИ
# ОБНОВЛЕНО: Теперь используют ColorService
# ========================================

def get_color(group):
    """
    Возвращает цвет в формате '#RRGGBB' для заданной группы.
    
    Это функция обратной совместимости, которая использует новый ColorService.
    
    Args:
        group (str): Название группы
        
    Returns:
        str: Цвет в формате '#RRGGBB'
    """
    try:
        return ColorService.get_color_for_group(group)
    except Exception as e:
        logger.error(f"Ошибка при генерации цвета для группы '{group}': {e}")
        return "#CCCCCC"  # Серый цвет по умолчанию при ошибке


# ========================================
# ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ ДЛЯ ЦВЕТОВ
# ========================================

def validate_color(color):
    """
    Проверяет валидность цвета.
    
    Args:
        color (str): Цвет для проверки
        
    Returns:
        bool: True если цвет валиден
    """
    return ColorService.validate_hex_color(color)


def get_color_palette(groups):
    """
    Генерирует палитру цветов для списка групп.
    
    Args:
        groups (list): Список названий групп
        
    Returns:
        dict: Словарь {группа: цвет}
    """
    return ColorService.get_color_palette_for_groups(groups)


# ========================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ФАЙЛАМИ И ПУТЯМИ
# ========================================

def ensure_directory_exists(directory_path):
    """
    Убеждается что директория существует, создает если нет.
    
    Args:
        directory_path (str): Путь к директории
        
    Returns:
        bool: True если директория существует или была создана
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Не удалось создать директорию {directory_path}: {e}")
        return False


def get_file_extension(filename):
    """
    Возвращает расширение файла.
    
    Args:
        filename (str): Имя файла
        
    Returns:
        str: Расширение файла (с точкой)
    """
    return os.path.splitext(filename)[1].lower()


def is_excel_file(filename):
    """
    Проверяет является ли файл Excel файлом.
    
    Args:
        filename (str): Имя файла
        
    Returns:
        bool: True если это Excel файл
    """
    excel_extensions = ['.xlsx', '.xls', '.xlsm']
    return get_file_extension(filename) in excel_extensions


# ========================================
# ИНФОРМАЦИОННЫЕ ФУНКЦИИ
# ========================================

def get_utils_info():
    """
    Возвращает информацию о модуле utils.
    
    Returns:
        dict: Словарь с метаинформацией
    """
    return {
        'version': '2.0.0',  # Увеличена версия после рефакторинга
        'color_service_version': ColorService.get_service_info()['version'],
        'modules': [
            'time_functions',
            'room_functions', 
            'color_functions',
            'file_functions'
        ],
        'refactored': True,
        'color_service_integration': True
    }


# ========================================
# DEPRECATED ФУНКЦИИ (для обратной совместимости)
# ========================================

# Глобальный словарь для сопоставления групп (DEPRECATED - используйте ColorService.COMPOUND_MAPPING)
COMPOUND_MAPPING = ColorService.COMPOUND_MAPPING.copy()

# Предупреждение об использовании deprecated констант
def _warn_deprecated_usage(item_name, new_location):
    """Показывает предупреждение об использовании устаревших элементов."""
    logger.warning(f"DEPRECATED: {item_name} устарел, используйте {new_location}")

# Функция для доступа к deprecated константам с предупреждением
def get_compound_mapping():
    """
    DEPRECATED: Используйте ColorService.COMPOUND_MAPPING
    
    Returns:
        dict: Словарь маппингов групп
    """
    _warn_deprecated_usage("get_compound_mapping()", "ColorService.COMPOUND_MAPPING")
    return ColorService.COMPOUND_MAPPING.copy()


# ========================================
# ТЕСТОВЫЕ ФУНКЦИИ (для отладки)
# ========================================

def test_color_generation():
    """
    Тестирует генерацию цветов для различных групп.
    Полезно для отладки и проверки работоспособности.
    """
    test_groups = [
        "2a", "4c", "2a+4c", "Schach 2a", "Tanz 4c", 
        "Deutsch 3b", "Gitarre", "10А", "empty_group", ""
    ]
    
    print("=== Тест генерации цветов ===")
    for group in test_groups:
        color = get_color(group)
        is_light = ColorService.is_light_color(color)
        contrast = ColorService.get_contrast_text_color(color)
        print(f"Группа: '{group}' → Цвет: {color} (Светлый: {is_light}, Текст: {contrast})")
    
    print(f"\nИнформация о ColorService: {ColorService.get_service_info()}")
    print(f"Информация о Utils: {get_utils_info()}")


if __name__ == "__main__":
    # Запуск тестов при прямом выполнении модуля
    test_color_generation()