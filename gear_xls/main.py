#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль программы генератора расписания.
Запускает графический интерфейс и координирует работу всех компонентов.
"""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import threading
import webbrowser

# Импортируем модули нашей программы
from excel_parser import parse_schedule
from schedule_structure import build_schedule_structure
from html_generator import generate_html_schedule
from pdf_generator import generate_pdf_schedule
from utils import create_output_directories

# Глобальная переменная для выбранного файла
selected_file = None
TIME_INTERVAL = 5  # Новый интервал времени в минутах (вместо 15)
BORDER_WIDTH = 0.5   # Толщина границы ячейки в пикселях
SERVER_PORT = 5000   # Порт для Flask-сервера

def choose_file():
    """Открывает диалог выбора файла и сохраняет путь к выбранному файлу."""
    global selected_file
    selected_file = filedialog.askopenfilename(
        title="Выберите файл с расписанием",
        filetypes=[("Excel файлы", "*.xlsx"), ("Все файлы", "*.*")]
    )
    if selected_file:
        file_button.config(text=f"Выбран: {selected_file}")
    else:
        file_button.config(text="Выберите Excel-файл с расписанием")

def run_script():
    """Запускает обработку выбранного файла и генерацию расписаний."""
    global selected_file
    if not selected_file:
        messagebox.showerror("Ошибка", "Пожалуйста, сначала выберите Excel файл!")
        return
    
    # Создаем директории для выходных файлов
    output_dirs = create_output_directories()
    
    try:
        # Выполняем обработку: парсинг Excel, генерация веб-страниц и PDF
        activities = parse_schedule(selected_file)
        if not activities:
            messagebox.showerror("Ошибка", "Не удалось извлечь данные о занятиях из Excel файла.")
            return
            
        buildings = build_schedule_structure(activities, time_interval=TIME_INTERVAL)
        if not buildings:
            messagebox.showerror("Ошибка", "Не удалось создать структуру расписания.")
            return
            
        html_file = os.path.join(output_dirs["html"], "schedule.html")
        generate_html_schedule(buildings, output_html=html_file, time_interval=TIME_INTERVAL, 
                              borderWidth=BORDER_WIDTH)
        
        generate_pdf_schedule(buildings, output_dir=output_dirs["pdf"], time_interval=TIME_INTERVAL)
        
        # Создаем директорию для экспорта Excel-файлов, если её нет
        excel_export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "excel_exports")
        if not os.path.exists(excel_export_dir):
            os.makedirs(excel_export_dir)
        
        # Запускаем веб-сервер в отдельном потоке для обработки запросов экспорта в Excel
        threading.Thread(target=start_flask_server, daemon=True).start()
        
        # Автоматически открываем веб-браузер с HTML-расписанием
        # webbrowser.open(f'file://{os.path.abspath(html_file)}')
        
        #messagebox.showinfo("Готово!", 
        #                  f"Веб-версия и PDF файлы успешно созданы.\n"
        #                  f"HTML: {os.path.abspath(output_dirs['html'])}\n"
        #                  f"PDF: {os.path.abspath(output_dirs['pdf'])}\n\n"
        #                  f"Расписание открыто в браузере.\n"
        #                  f"Для экспорта в Excel используйте кнопку 'Экспорт в Excel' в веб-интерфейсе."
        #                  f"Функция экспорта будет работать до тех пор пока запущен"
        #                  f"Flask-сервер.")
        
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()

def start_flask_server():
    """Запускает Flask-сервер в отдельном потоке."""
    try:
        # Импортируем Flask-приложение здесь, чтобы избежать циклических импортов
        import subprocess
        import os
        import sys
        
        # Путь к скрипту server_routes.py
        server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_routes.py")
        
        # Проверяем существование файла
        if not os.path.exists(server_script):
            print(f"Ошибка: файл {server_script} не найден")
            return
        
        # Запускаем сервер в отдельном процессе
        print(f"Запуск Flask-сервера: {server_script}")
        
        # Используем текущий интерпретатор Python
        python_exec = sys.executable
        
        # На Windows используем create_new_console для создания нового окна
        if os.name == 'nt':  # Windows
            subprocess.Popen(
                [python_exec, server_script],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:  # Linux, Mac и другие системы
            subprocess.Popen(
                [python_exec, server_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        
        print("Flask-сервер запущен в отдельном процессе")
        print("Функция экспорта будет работать до тех пор пока запущен процесс Flask-сервера")
        
    except Exception as e:
        print(f"Ошибка при запуске Flask-сервера: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Основная функция, создающая и запускающая GUI приложение."""
    global file_button
    
    # Создаем главное окно
    root = tk.Tk()
    root.title("Генератор расписания из Excel")

    # Параметры окна
    root.geometry("550x250")
    root.resizable(False, False)

    # Создаем фрейм для размещения кнопок с отступами
    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack(expand=True, fill='both')

    # Добавляем заголовок
    title_label = tk.Label(
        frame, 
        text="Генератор расписания из Excel-файла", 
        font=("Arial", 14, "bold")
    )
    title_label.pack(pady=(0, 15))

    # Кнопка для выбора Excel файла
    file_button = tk.Button(
        frame, 
        text="Выберите Excel-файл с расписанием", 
        command=choose_file, 
        width=50,
        height=2
    )
    file_button.pack(pady=10)

    # Кнопка для запуска обработки (генерации веб-версии и PDF)
    run_button = tk.Button(
        frame, 
        text="Создать веб-приложение для редактирования расписания", 
        command=run_script, 
        width=50,
        height=2,
        bg="#90ee90"  # Нежно-зеленый фон для кнопки запуска
    )
    run_button.pack(pady=10)
    
    # Информационная метка о функции экспорта
    info_label = tk.Label(
        frame,
        text="Примечание: В веб-версии расписания будет доступна кнопка\n'Экспорт в Excel' для обратного преобразования",
        font=("Arial", 9),
        fg="#555555"
    )
    info_label.pack(pady=5)

    # Запуск главного цикла обработки событий
    root.mainloop()

if __name__ == "__main__":
    main()
