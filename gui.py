import tkinter as tk
from tkinter import ttk

# Импорт модулей из gui_services
from gui_services import UIBuilder, FileManager, ProcessManager, AppActions, Logger


class ApplicationInterface:
    def __init__(self, root):
        self.root = root
        
        # Настройка главного окна
        UIBuilder.create_main_window(root)
        
        # Создание основного фрейма
        main_frame = UIBuilder.create_main_frame(root)
        
        # Заголовок
        UIBuilder.create_title_label(main_frame)
        
        # Информационная панель
        info_frame = UIBuilder.create_info_frame(main_frame)
        self.dir_label, self.file_label = UIBuilder.create_info_labels(info_frame)
        
        # Контейнер для кнопок
        buttons_frame = UIBuilder.create_buttons_frame(main_frame)
        
        # Лог действий
        log_frame = UIBuilder.create_log_frame(main_frame)
        log_text = UIBuilder.create_log_text(log_frame)
        
        # Статус бар  
        status_bar = UIBuilder.create_status_bar(root)
        
        # Инициализация сервисов
        self.process_manager = ProcessManager()
        self.logger = Logger(log_text, status_bar, root)
        self.app_actions = AppActions(self.process_manager, self.logger.log_action)
        
        # Создание кнопок интерфейса
        self._create_buttons(buttons_frame)
    
    def _create_buttons(self, buttons_frame):
        """Создание всех кнопок интерфейса"""
        
        # Кнопка 1: Выбор рабочего каталога
        UIBuilder.create_single_button(
            buttons_frame, 
            "1. Выбрать рабочий каталог", 
            self._handle_select_directory
        )
        
        # Кнопки 2: Оптимизация
        UIBuilder.create_double_button_row(
            buttons_frame,
            "2. Запустить оптимизацию", self.app_actions.run_scheduler,
            "2.1. Открыть оптимизированное расписание", self.app_actions.open_optimized_schedule
        )
        
        # Кнопки 3: Веб-приложение
        UIBuilder.create_triple_button_row(
            buttons_frame,
            "3. Создать веб-приложение", self.app_actions.run_gear_xls,
            "3.1. Запустить flask-сервер", self.app_actions.run_flask_server,
            "3.2. Открыть веб-приложение", self.app_actions.open_web_app
        )
        
        # Кнопки 4: Визуализация
        UIBuilder.create_triple_button_row(
            buttons_frame,
            "4. Запустить визуализатор", self.app_actions.run_visualiser,
            "4.1. Открыть PDF-визуализацию", self.app_actions.open_pdf_visualization,
            "4.2. Открыть HTML-визуализацию", self.app_actions.open_html_visualization
        )
        
        # Кнопка 5: Выбор файла
        UIBuilder.create_single_button(
            buttons_frame, 
            "5. Выбрать .xlsx файл", 
            self._handle_select_xlsx_file
        )
        
        # Кнопки 6: Конвертация
        UIBuilder.create_double_button_row(
            buttons_frame,
            "6. Конвертировать в .xlsm", self.app_actions.convert_to_xlsm,
            "6.1. Открыть .xlsm файл", self.app_actions.open_xlsm_file
        )
        
        # Кнопки 7: Работа с новыми предпочтениями
        UIBuilder.create_double_button_row(
            buttons_frame,
            "7.0. Открыть новые предпочтения", self.app_actions.open_newpref,
            "7. Учесть изменения", self.app_actions.run_scheduler_newpref
        )
    
    def _handle_select_directory(self):
        """Обработчик выбора рабочего каталога с обновлением интерфейса"""
        directory = self.app_actions.select_directory()
        if directory:
            self.app_actions.set_program_directory(directory)
            self.dir_label.config(text=f"Рабочий каталог: {directory}")
    
    def _handle_select_xlsx_file(self):
        """Обработчик выбора xlsx файла с обновлением интерфейса"""
        filename = self.app_actions.select_xlsx_file()
        if filename:
            self.file_label.config(text=f"Выбранный файл: {filename}")


if __name__ == "__main__":
    # Создаем экземпляр Tk
    root = tk.Tk()
    
    # Создаем приложение
    app = ApplicationInterface(root)
    
    # Запускаем основной цикл
    root.mainloop()