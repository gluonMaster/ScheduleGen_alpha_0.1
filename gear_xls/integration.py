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

# Импортируем новый сервис пайплайна
from services.schedule_pipeline import SchedulePipeline, SchedulePipelineError
from utils import create_output_directories

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('integration')

# Константы конфигурации
DEFAULT_TIME_INTERVAL = 5
DEFAULT_BORDER_WIDTH = 0.5


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
        import sys
        
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


def run_full_pipeline(excel_file_path: str,                     time_interval: int = DEFAULT_TIME_INTERVAL,
                     border_width: float = DEFAULT_BORDER_WIDTH,
                     open_browser: bool = True,
                     start_server: bool = True) -> bool:
    """
    Запускает полный процесс обработки Excel-файла:
    1. Парсинг Excel и генерация HTML
    2. Запуск Flask-сервера для обработки запросов экспорта (опционально)
    3. Открытие HTML-версии в браузере (опционально)
    
    Args:
        excel_file_path (str): Путь к исходному Excel-файлу
        time_interval (int): Интервал времени в минутах для сетки расписания
        border_width (float): Толщина границ ячеек в пикселях  
        open_browser (bool): Открывать ли браузер автоматически
        start_server (bool): Запускать ли Flask-сервер
        
    Returns:
        bool: True если процесс успешно запущен, False в случае ошибки
    """
    logger.info(f"Запуск полного пайплайна для файла: {excel_file_path}")
    logger.info(f"Параметры: interval={time_interval}, border={border_width}, "
               f"browser={open_browser}, server={start_server}")
    
    try:
        # Проверяем наличие файла
        if not os.path.exists(excel_file_path):
            logger.error(f"Excel-файл не найден: {excel_file_path}")
            return False
        
        # Настраиваем окружение
        if not setup_environment():
            logger.error("Не удалось подготовить окружение")
            return False
        
        # Создаем директории для выходных файлов
        output_dirs = create_output_directories()
        
        # Создаем экземпляр пайплайна с указанными настройками
        pipeline = SchedulePipeline(
            time_interval=time_interval,
            border_width=border_width
        )
        
        # Выполняем основную обработку
        logger.info("Запуск обработки через SchedulePipeline...")
        result = pipeline.process_excel_to_outputs(excel_file_path, output_dirs)
          # Логируем подробные результаты
        logger.info("Обработка завершена успешно:")
        logger.info(f"  - Входной файл: {excel_file_path}")
        logger.info(f"  - Занятий обработано: {result['activities_count']}")
        logger.info(f"  - Зданий создано: {result['buildings_count']}")
        logger.info(f"  - HTML файл: {result['html_file']}")
        
        # Запускаем Flask-сервер для обработки запросов экспорта (если требуется)
        server_process = None
        if start_server:
            logger.info("Запуск Flask-сервера...")
            server_process = start_flask_server_subprocess()
            if server_process:
                logger.info("Flask-сервер успешно запущен")
            else:
                logger.warning("Не удалось запустить Flask-сервер, экспорт в Excel будет недоступен")
        
        # Открываем HTML-файл в браузере (если требуется)
        if open_browser and os.path.exists(result['html_file']):
            logger.info("Открытие HTML-расписания в браузере...")
            webbrowser.open(f'file://{os.path.abspath(result["html_file"])}')
            logger.info(f"HTML-расписание открыто в браузере: {result['html_file']}")
        
        logger.info("Полный процесс обработки завершен успешно")
        return True
        
    except SchedulePipelineError as e:
        logger.error(f"Ошибка пайплайна при обработке: {e}")
        return False
        
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске полного процесса: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_and_run_pipeline(excel_file_path: str, **kwargs) -> bool:
    """
    Проверяет файл и запускает пайплайн только если файл валиден.
    
    Args:
        excel_file_path (str): Путь к Excel файлу
        **kwargs: Дополнительные параметры для run_full_pipeline
        
    Returns:
        bool: True если валидация прошла и пайплайн запущен успешно
    """
    logger.info(f"Валидация файла: {excel_file_path}")
    
    # Быстрая проверка валидности
    pipeline = SchedulePipeline()
    if not pipeline.validate_excel_file(excel_file_path):
        logger.error(f"Файл не прошел валидацию: {excel_file_path}")
        return False
    
    logger.info("Файл прошел валидацию, запуск полного пайплайна...")
    return run_full_pipeline(excel_file_path, **kwargs)


def get_pipeline_status() -> dict:
    """
    Возвращает информацию о состоянии пайплайна и доступных возможностях.
    
    Returns:
        dict: Словарь со статусом компонентов системы
    """
    status = {
        'pipeline_available': True,
        'environment_ready': False,
        'server_script_exists': False,
        'output_dirs_exist': False
    }
    
    try:
        # Проверяем готовность окружения
        status['environment_ready'] = setup_environment()
        
        # Проверяем наличие скрипта сервера
        server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_routes.py")
        status['server_script_exists'] = os.path.exists(server_script)
        
        # Проверяем наличие выходных директорий
        output_dirs = create_output_directories()
        status['output_dirs_exist'] = all(os.path.exists(d) for d in output_dirs.values())
        
        # Получаем информацию о версии пайплайна
        pipeline = SchedulePipeline()
        status['pipeline_info'] = pipeline.get_pipeline_info()
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}")
        status['error'] = str(e)
    
    return status


if __name__ == "__main__":
    import sys
    
    # Если передан аргумент - используем его как путь к файлу
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
        
        # Дополнительные параметры из командной строки
        time_interval = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_TIME_INTERVAL
        border_width = float(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_BORDER_WIDTH
        
        success = run_full_pipeline(
            excel_file,
            time_interval=time_interval,
            border_width=border_width
        )
        
        sys.exit(0 if success else 1)
    else:
        print("Использование: python integration.py путь_к_excel_файлу.xlsx [интервал_времени] [толщина_границ]")
        print(f"По умолчанию: интервал={DEFAULT_TIME_INTERVAL}, границы={DEFAULT_BORDER_WIDTH}")
        
        # Показываем статус системы
        status = get_pipeline_status()
        print(f"\nСтатус системы:")
        for key, value in status.items():
            print(f"  {key}: {value}")
            