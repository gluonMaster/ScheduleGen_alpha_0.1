#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль с маршрутами для веб-сервера Flask, обрабатывающий
запросы на экспорт расписания в Excel.
"""

import os
import json
import logging
import sys
from flask import Flask, request, send_file, jsonify, redirect, url_for
from excel_exporter import process_schedule_export_request
from flask_cors import CORS  # Добавьте эту строку в начале файла

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('flask_server.log')
    ]
)
logger = logging.getLogger('server_routes')

# Создаем Flask-приложение
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Разрешить запросы с любого источник

# Директория для хранения экспортированных Excel-файлов
EXCEL_EXPORTS_DIR = "excel_exports"

# Проверяем, существует ли директория, и создаем, если нет
if not os.path.exists(EXCEL_EXPORTS_DIR):
    os.makedirs(EXCEL_EXPORTS_DIR)
    logger.info(f"Создана директория для экспорта: {EXCEL_EXPORTS_DIR}")
else:
    logger.info(f"Директория для экспорта существует: {EXCEL_EXPORTS_DIR}")

@app.route('/')
def index():
    """Корневой маршрут для проверки работы сервера"""
    logger.info("Получен запрос к корневому маршруту")
    return "Excel Export Server is running! Access /export_to_excel via POST request to export schedule."

@app.route('/export_to_excel', methods=['POST'])
def export_to_excel():
    """
    Обрабатывает POST-запрос на экспорт расписания в Excel.
    Ожидает JSON-данные в поле 'schedule_data' формы.
    """
    try:
        # Получаем данные из запроса
        schedule_data_json = request.form.get('schedule_data')
        csrf_token = request.form.get('csrf_token', '')
        
        if not schedule_data_json:
            logger.error("Данные расписания не получены")
            return jsonify({"error": "Данные расписания не получены"}), 400
        
        logger.info(f"Получены данные для экспорта в Excel (CSRF: {csrf_token[:8] if csrf_token else 'отсутствует'})")
        logger.info(f"Размер данных: {len(schedule_data_json)} байт")
        
        # Для предотвращения CSRF-атак в реальном приложении здесь нужно проверить 
        # валидность токена, но для демонстрации просто логируем его наличие
        
        # Обрабатываем запрос и создаем Excel-файл
        output_file = process_schedule_export_request(schedule_data_json, EXCEL_EXPORTS_DIR)
        
        if not output_file or not os.path.exists(output_file):
            logger.error("Не удалось создать Excel-файл")
            return jsonify({"error": "Не удалось создать Excel-файл"}), 500
        
        logger.info(f"Файл готов к отправке: {output_file}")
        
        # Настраиваем заголовки CORS для разрешения запросов с локального файла
        response = send_file(
            output_file,
            as_attachment=True,
            download_name=os.path.basename(output_file),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Добавляем CORS-заголовки для безопасного скачивания
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        
        logger.info(f"Excel-файл успешно отправлен: {output_file}")
        return response
    
    except Exception as e:
        logger.error(f"Ошибка при экспорте в Excel: {e}")
        import traceback
        traceback.print_exc()
        
        # Добавляем CORS-заголовки даже для ответов с ошибкой
        response = jsonify({"error": str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500
        
# Добавляем поддержку предварительных запросов OPTIONS для CORS
@app.route('/export_to_excel', methods=['OPTIONS'])
def export_to_excel_options():
    """Обрабатывает предварительные запросы OPTIONS для CORS"""
    response = app.make_default_options_response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response

# Точка входа для запуска сервера
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    logger.info(f"Запуск Flask-сервера на {host}:{port}")
    print(f"=== Запуск сервера экспорта в Excel на {host}:{port} ===")
    print(f"=== Журнал работы в файле: flask_server.log ===")
    app.run(debug=True, host=host, port=port)