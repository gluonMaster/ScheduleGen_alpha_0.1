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
        
        # Инициализация сервисов (без logger пока)
        self.process_manager = ProcessManager()
        self.app_actions = AppActions(self.process_manager)  # Без log_callback
        
        # Информационная панель
        info_frame = UIBuilder.create_info_frame(main_frame)
        self.dir_label, _ = UIBuilder.create_info_labels(info_frame)  # file_label больше не используется
        
        # Контейнер для кнопок
        buttons_frame = UIBuilder.create_buttons_frame(main_frame)
        
        # Лог действий
        log_frame = UIBuilder.create_log_frame(main_frame)
        log_text = UIBuilder.create_log_text(log_frame)
        
        # Статус бар  
        status_bar = UIBuilder.create_status_bar(root)
        
        # Теперь инициализируем logger и устанавливаем его в app_actions
        self.logger = Logger(log_text, status_bar, root)
        self.app_actions.set_log_callback(self.logger.log_action)
        
        # Обновляем информацию о каталоге
        if self.app_actions.get_program_directory():
            directory = self.app_actions.get_program_directory()
            # Показываем только имя каталога, если путь слишком длинный
            if len(directory) > 60:
                display_dir = "..." + directory[-57:]
            else:
                display_dir = directory
            self.dir_label.config(text=f"Рабочий каталог: {display_dir}")
        else:
            self.dir_label.config(text="⚠ Рабочий каталог: не определен автоматически")
        
        # Создание кнопок интерфейса
        self._create_buttons(buttons_frame)
    
    def _create_buttons(self, buttons_frame):
        """Создание всех кнопок интерфейса"""
        
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
        
        # Кнопки 7: Работа с новыми предпочтениями
        UIBuilder.create_double_button_row(
            buttons_frame,
            "7.0. Создать и открыть новые предпочтения", self.app_actions.open_newpref,
            "7. Учесть изменения", self.app_actions.run_scheduler_newpref
        )

if __name__ == "__main__":
    # Создаем экземпляр Tk
    root = tk.Tk()
    
    # Создаем приложение
    app = ApplicationInterface(root)
    
    # Запускаем основной цикл
    root.mainloop()