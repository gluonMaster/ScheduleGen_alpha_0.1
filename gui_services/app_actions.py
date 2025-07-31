import os
import threading
import time
from tkinter import messagebox
from .file_manager import FileManager
from .process_manager import ProcessManager


class AppActions:
    """Действия приложения"""
    
    def __init__(self, process_manager: ProcessManager, log_callback):
        self.process_manager = process_manager
        self.log_action = log_callback
        self.program_directory = None
        self.selected_xlsx_file = None
    
    def set_program_directory(self, directory):
        """Установка рабочего каталога"""
        self.program_directory = directory
    
    def set_selected_file(self, file_path):
        """Установка выбранного файла"""
        self.selected_xlsx_file = file_path
    
    def select_directory(self):
        """Обработчик для кнопки 1: Выбор рабочего каталога"""
        directory = FileManager.select_directory("Выберите рабочий каталог программы")
        if directory:
            self.program_directory = directory
            self.log_action(f"Выбран рабочий каталог: {directory}")
            return directory
        return None
    
    def run_scheduler(self):
        """Обработчик для кнопки 2: Запуск планировщика"""
        if not self._check_directory():
            return
        
        self.log_action("Запуск планировщика...")
        
        commands = [
            "python main_sch.py xlsx_initial/schedule_planning.xlsx --time-limit 300 --verbose --time-interval 5"
        ]
        
        def run_in_thread():
            self.process_manager.terminal_process = self.process_manager.execute_in_terminal(
                commands, self.program_directory)
        
        threading.Thread(target=run_in_thread, daemon=True).start()
    
    def open_optimized_schedule(self):
        """Обработчик для кнопки 2.1: Открытие оптимизированного расписания"""
        if not self._check_directory():
            return
        
        file_path = FileManager.get_file_path(self.program_directory, "visualiser", "optimized_schedule.xlsx")
        if FileManager.open_file(file_path, "оптимизированное расписание"):
            self.log_action(f"Открыт файл: {file_path}")
    
    def run_gear_xls(self):
        """Обработчик для кнопки 3: Запуск gear_xls"""
        if not self._check_directory():
            return
        
        self.log_action("Запуск gear_xls...")
        
        gear_dir = FileManager.get_file_path(self.program_directory, "gear_xls")
        commands = ["python main.py"]
        
        def run_in_thread():
            self.process_manager.terminal_process = self.process_manager.execute_in_terminal(
                commands, gear_dir)
        
        threading.Thread(target=run_in_thread, daemon=True).start()
    
    def run_flask_server(self):
        """Обработчик для кнопки 3.1: Запуск flask-сервера"""
        if not self._check_directory():
            return
        
        if self.process_manager.is_process_running(self.process_manager.flask_process):
            messagebox.showinfo("Информация", "Flask-сервер уже запущен")
            return
        
        self.log_action("Запуск flask-сервера...")
        
        def run_in_thread():
            self.process_manager.flask_process = self.process_manager.start_new_terminal_with_commands(
                self.program_directory)
            time.sleep(1)
            self.log_action("Терминал flask-сервера запущен. Пока окно терминала открыто Вы можете экспортировать расписание из веб-приложения в эксель-файл")
        
        threading.Thread(target=run_in_thread, daemon=True).start()
    
    def open_web_app(self):
        """Обработчик для кнопки 3.2: Открытие веб-приложения"""
        if not self._check_directory():
            return
        
        html_path = FileManager.get_file_path(self.program_directory, "gear_xls", "html_output", "schedule.html")
        if FileManager.open_web_file(html_path, "веб-приложение"):
            self.log_action(f"Открыто веб-приложение: {html_path}")
    
    def run_visualiser(self):
        """Обработчик для кнопки 4: Запуск визуализатора"""
        if not self._check_directory():
            return
        
        self.log_action("Запуск визуализатора...")
        
        visualiser_dir = FileManager.get_file_path(self.program_directory, "visualiser")
        commands = ["python example_usage_enhanced.py"]
        
        def run_in_thread():
            self.process_manager.terminal_process = self.process_manager.execute_in_terminal(
                commands, visualiser_dir)
        
        threading.Thread(target=run_in_thread, daemon=True).start()
    
    def open_pdf_visualization(self):
        """Обработчик для кнопки 4.1: Открытие PDF-визуализации"""
        if not self._check_directory():
            return
        
        file_path = FileManager.get_file_path(self.program_directory, "visualiser", "enhanced_schedule_visualization.pdf")
        if FileManager.open_file(file_path, "PDF-визуализацию"):
            self.log_action(f"Открыт файл: {file_path}")
    
    def open_html_visualization(self):
        """Обработчик для кнопки 4.2: Открытие HTML-визуализации"""
        if not self._check_directory():
            return
        
        file_path = FileManager.get_file_path(self.program_directory, "visualiser", "enhanced_schedule_visualization.html")
        if FileManager.open_web_file(file_path, "HTML-визуализацию"):
            self.log_action(f"Открыт файл: {file_path}")
    
    def select_xlsx_file(self):
        """Обработчик для кнопки 5: Выбор .xlsx файла"""
        if not self._check_directory():
            return
        
        excel_dir = FileManager.get_file_path(self.program_directory, "gear_xls", "excel_exports")
        xlsx_file = FileManager.select_xlsx_file(excel_dir, "Выберите .xlsx файл")
        
        if xlsx_file:
            self.selected_xlsx_file = xlsx_file
            filename = os.path.basename(xlsx_file)
            self.log_action(f"Выбран файл: {filename}")
            return filename
        return None
    
    def convert_to_xlsm(self):
        """Обработчик для кнопки 6: Конвертирование в .xlsm"""
        if not self._check_directory():
            return
        
        if not self.selected_xlsx_file:
            messagebox.showwarning("Предупреждение", "Сначала выберите .xlsx файл (шаг 5)")
            return
        
        self.log_action("Конвертирование в .xlsm...")
        
        xlsx_filename = os.path.basename(self.selected_xlsx_file)
        commands = [f"python convert_to_xlsm.py excel_exports/{xlsx_filename}"]
        
        def run_in_thread():
            self.process_manager.terminal_process = self.process_manager.execute_in_terminal(
                commands, FileManager.get_file_path(self.program_directory, "gear_xls"))
        
        threading.Thread(target=run_in_thread, daemon=True).start()
    
    def open_xlsm_file(self):
        """Обработчик для кнопки 6.1: Открытие .xlsm файла"""
        if not self._check_directory():
            return
        
        if not self.selected_xlsx_file:
            messagebox.showwarning("Предупреждение", "Сначала выберите .xlsx файл (шаг 5)")
            return
        
        xlsx_filename = os.path.basename(self.selected_xlsx_file)
        base_name = os.path.splitext(xlsx_filename)[0]
        
        xlsm_path = FileManager.get_file_path(self.program_directory, "gear_xls", "excel_exports", f"{base_name}.xlsm")
        
        if not FileManager.check_directory_exists(xlsm_path):
            messagebox.showwarning("Предупреждение", 
                                  f"Файл .xlsm не найден: {xlsm_path}\n\nСначала конвертируйте .xlsx файл в .xlsm (кнопка 6)")
            return
        
        if FileManager.open_file(xlsm_path, ".xlsm файл"):
            self.log_action(f"Открыт файл: {xlsm_path}")
    
    def open_newpref(self):
        """Обработчик для кнопки 7.0: Открытие файла newpref.xlsx"""
        if not self._check_directory():
            return
        
        file_path = FileManager.get_file_path(self.program_directory, "xlsx_initial", "newpref.xlsx")
        if FileManager.open_file(file_path, "newpref.xlsx"):
            self.log_action(f"Открыт файл: {file_path}")
    
    def run_scheduler_newpref(self):
        """Обработчик для кнопки 7: Запуск планировщика с newpref.xlsx"""
        if not self._check_directory():
            return
        
        self.log_action("Запуск планировщика с newpref.xlsx...")
        
        commands = [
            "python main_sch.py xlsx_initial/newpref.xlsx --time-limit 300 --verbose --time-interval 5"
        ]
        
        def run_in_thread():
            self.process_manager.terminal_process = self.process_manager.execute_in_terminal(
                commands, self.program_directory)
        
        threading.Thread(target=run_in_thread, daemon=True).start()
    
    def _check_directory(self):
        """Проверка установки рабочего каталога"""
        if not self.program_directory:
            messagebox.showwarning("Предупреждение", "Сначала выберите рабочий каталог программы")
            return False
        return True
