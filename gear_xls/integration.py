#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционный модуль для объединения функциональности генерации расписания 
и экспорта обратно в Excel.
"""

import os
import shutil
import logging
import subprocess
import time
import webbrowser
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('integration')

def setup_environment():
    """
    Подготавливает окружение для работы приложения:
    - Создает необходимые директории
    - Копирует JavaScript модуль export_to_excel.js в директорию с JS-модулями
    
    Returns:
        bool: True если подготовка успешна, False в случае ошибки
    """
    try:
        # Определяем текущую директорию
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Создаем директории для выходных файлов
        output_dirs = [
            os.path.join(current_dir, "html_output"),
            os.path.join(current_dir, "pdfs"),
            os.path.join(current_dir, "excel_exports"),
            os.path.join(current_dir, "js_modules")
        ]
        
        for directory in output_dirs:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Директория {directory} создана или уже существует")
        
        # Копируем модуль export_to_excel.js в директорию с JS-модулями
        export_js_src = os.path.join(current_dir, "export_to_excel.js")
        export_js_dst = os.path.join(current_dir, "js_modules", "export_to_excel.js")
        
        if os.path.exists(export_js_src):
            shutil.copy2(export_js_src, export_js_dst)
            logger.info(f"Модуль export_to_excel.js скопирован в {export_js_dst}")
        else:
            logger.warning(f"Модуль export_to_excel.js не найден в {export_js_src}")
        
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при подготовке окружения: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_flask_server_subprocess():
    """
    Запускает Flask-сервер в отдельном процессе для обработки запросов экспорта.
    
    Returns:
        subprocess.Popen: Процесс Flask-сервера или None в случае ошибки
    """
    try:
        # Запускаем server_routes.py как отдельный процесс
        server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_routes.py")
        
        # Проверяем, что файл существует
        if not os.path.exists(server_script):
            logger.error(f"Скрипт сервера не найден: {server_script}")
            return None
        
        # Запускаем процесс
        process = subprocess.Popen(
            [sys.executable, server_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        logger.info(f"Flask-сервер запущен с PID {process.pid}")
        
        # Небольшая пауза, чтобы сервер успел запуститься
        time.sleep(1)
        
        return process
    
    except Exception as e:
        logger.error(f"Ошибка при запуске Flask-сервера: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_full_pipeline(excel_file_path):
    """
    Запускает полный процесс обработки Excel-файла:
    1. Парсинг Excel и генерация HTML/PDF
    2. Запуск Flask-сервера для обработки запросов экспорта
    3. Открытие HTML-версии в браузере
    
    Args:
        excel_file_path (str): Путь к исходному Excel-файлу
        
    Returns:
        bool: True если процесс успешно запущен, False в случае ошибки
    """
    try:
        # Проверяем наличие файла
        if not os.path.exists(excel_file_path):
            logger.error(f"Excel-файл не найден: {excel_file_path}")
            return False
        
        # Настраиваем окружение
        if not setup_environment():
            logger.error("Не удалось подготовить окружение")
            return False
        
        # Импортируем основные модули
        from excel_parser import parse_schedule
        from schedule_structure import build_schedule_structure
        from html_generator import generate_html_schedule
        from pdf_generator import generate_pdf_schedule
        from utils import create_output_directories
        
        # Создаем директории для выходных файлов
        output_dirs = create_output_directories()
        
        # Парсим Excel-файл
        activities = parse_schedule(excel_file_path)
        if not activities:
            logger.error("Не удалось извлечь данные о занятиях из Excel файла")
            return False
        
        # Строим структуру расписания
        buildings = build_schedule_structure(activities, time_interval=5)
        if not buildings:
            logger.error("Не удалось создать структуру расписания")
            return False
        
        # Генерируем HTML-расписание
        html_file = os.path.join(output_dirs["html"], "schedule.html")
        generate_html_schedule(buildings, output_html=html_file, time_interval=5, borderWidth=0.5)
        
        # Генерируем PDF-расписание
        generate_pdf_schedule(buildings, output_dir=output_dirs["pdf"], time_interval=5)
        
        # Запускаем Flask-сервер для обработки запросов экспорта
        server_process = start_flask_server_subprocess()
        
        # Открываем HTML-файл в браузере
        if os.path.exists(html_file):
            webbrowser.open(f'file://{os.path.abspath(html_file)}')
            logger.info(f"HTML-расписание открыто в браузере: {html_file}")
        
        logger.info("Полный процесс обработки запущен успешно")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при запуске полного процесса: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    # Если передан аргумент - используем его как путь к файлу
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
        run_full_pipeline(excel_file)
    else:
        print("Использование: python integration.py путь_к_excel_файлу.xlsx")
