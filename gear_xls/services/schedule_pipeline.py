#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для обработки пайплайна создания расписания.
Инкапсулирует общую логику преобразования Excel → HTML + PDF.
"""

import os
import logging
from typing import Dict, Any, Optional

# Импортируем существующие модули
from excel_parser import parse_schedule
from schedule_structure import build_schedule_structure
from html_generator import generate_html_schedule
from pdf_generator import generate_pdf_schedule

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('schedule_pipeline')


class SchedulePipelineError(Exception):
    """Исключение для ошибок в пайплайне обработки расписания"""
    pass


class SchedulePipeline:
    """
    Сервис для координации процесса создания расписания из Excel файла.
    
    Инкапсулирует весь пайплайн: парсинг → структурирование → генерация HTML и PDF
    """
    
    def __init__(self, time_interval: int = 5, border_width: float = 0.5):
        """
        Инициализация пайплайна с настройками по умолчанию.
        
        Args:
            time_interval (int): Интервал времени в минутах для сетки расписания
            border_width (float): Толщина границ ячеек в пикселях
        """
        self.time_interval = time_interval
        self.border_width = border_width
        logger.info(f"Инициализирован SchedulePipeline: interval={time_interval}мин, border={border_width}px")
    
    def process_excel_to_outputs(self, excel_file_path: str, output_dirs: Dict[str, str]) -> Dict[str, Any]:
        """
        Обрабатывает Excel файл и создает HTML и PDF выходные файлы.
        
        Args:
            excel_file_path (str): Путь к исходному Excel файлу
            output_dirs (Dict[str, str]): Словарь с путями к директориям вывода
                                        (должен содержать ключи 'html' и 'pdf')
        
        Returns:
            Dict[str, Any]: Словарь с результатами обработки:
                - html_file: путь к созданному HTML файлу
                - buildings: структура расписания по зданиям
                - activities_count: количество обработанных занятий
                - pdf_files: список созданных PDF файлов
        
        Raises:
            SchedulePipelineError: При ошибках на любом этапе обработки
        """
        logger.info(f"Начинаем обработку файла: {excel_file_path}")
        
        # Проверяем существование входного файла
        if not os.path.exists(excel_file_path):
            raise SchedulePipelineError(f"Excel файл не найден: {excel_file_path}")
        
        # Проверяем наличие выходных директорий
        required_dirs = ['html', 'pdf']
        for dir_key in required_dirs:
            if dir_key not in output_dirs:
                raise SchedulePipelineError(f"Не указана директория для {dir_key}")
            if not os.path.exists(output_dirs[dir_key]):
                raise SchedulePipelineError(f"Директория не существует: {output_dirs[dir_key]}")
        
        try:
            # Этап 1: Парсинг Excel файла
            logger.info("Этап 1: Парсинг Excel файла...")
            activities = parse_schedule(excel_file_path)
            if not activities:
                raise SchedulePipelineError("Не удалось извлечь данные о занятиях из Excel файла. "
                                          "Проверьте формат файла и наличие листа 'Schedule'.")
            
            activities_count = len(activities)
            logger.info(f"Успешно извлечено {activities_count} занятий")
            
            # Этап 2: Построение структуры расписания
            logger.info("Этап 2: Построение структуры расписания...")
            buildings = build_schedule_structure(activities, time_interval=self.time_interval)
            if not buildings:
                raise SchedulePipelineError("Не удалось создать структуру расписания из извлеченных данных.")
            
            buildings_count = len([b for b in buildings.keys() if not b.startswith('_')])
            logger.info(f"Успешно построена структура для {buildings_count} зданий")
            
            # Этап 3: Генерация HTML
            logger.info("Этап 3: Генерация HTML файла...")
            html_file = os.path.join(output_dirs["html"], "schedule.html")
            generate_html_schedule(
                buildings, 
                output_html=html_file, 
                time_interval=self.time_interval,
                borderWidth=self.border_width
            )
            
            if not os.path.exists(html_file):
                raise SchedulePipelineError(f"HTML файл не был создан: {html_file}")
            
            logger.info(f"HTML файл создан: {html_file}")
            
            # Этап 4: Генерация PDF
            logger.info("Этап 4: Генерация PDF файлов...")
            generate_pdf_schedule(
                buildings, 
                output_dir=output_dirs["pdf"], 
                time_interval=self.time_interval
            )
            
            # Проверяем созданные PDF файлы
            pdf_files = []
            for building in buildings.keys():
                if not building.startswith('_'):
                    pdf_file = os.path.join(output_dirs["pdf"], f"{building}.pdf")
                    if os.path.exists(pdf_file):
                        pdf_files.append(pdf_file)
            
            logger.info(f"Создано {len(pdf_files)} PDF файлов")
            
            # Формируем результат
            result = {
                'html_file': html_file,
                'buildings': buildings,
                'activities_count': activities_count,
                'pdf_files': pdf_files,
                'buildings_count': buildings_count
            }
            
            logger.info(f"Обработка завершена успешно. Обработано {activities_count} занятий, "
                       f"создано {buildings_count} зданий, {len(pdf_files)} PDF файлов")
            
            return result
            
        except Exception as e:
            # Логируем подробную информацию об ошибке
            logger.error(f"Ошибка при обработке файла {excel_file_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # Перебрасываем как SchedulePipelineError для единообразной обработки
            if isinstance(e, SchedulePipelineError):
                raise
            else:
                raise SchedulePipelineError(f"Внутренняя ошибка при обработке: {e}")
    
    def validate_excel_file(self, excel_file_path: str) -> bool:
        """
        Быстрая проверка валидности Excel файла без полной обработки.
        
        Args:
            excel_file_path (str): Путь к Excel файлу
            
        Returns:
            bool: True если файл можно обработать, False иначе
        """
        try:
            if not os.path.exists(excel_file_path):
                return False
            
            # Пытаемся извлечь хотя бы одно занятие
            activities = parse_schedule(excel_file_path)
            return bool(activities)
            
        except Exception as e:
            logger.warning(f"Файл {excel_file_path} не прошел валидацию: {e}")
            return False
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о текущих настройках пайплайна.
        
        Returns:
            Dict[str, Any]: Словарь с настройками пайплайна
        """
        return {
            'time_interval': self.time_interval,
            'border_width': self.border_width,
            'version': '1.0.0'
        }
    