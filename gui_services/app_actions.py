import os
import sys
import glob
import threading
import time
import win32com.client
import pythoncom
from tkinter import messagebox
from .file_manager import FileManager
from .process_manager import ProcessManager


class AppActions:
    """Действия приложения"""
    
    def __init__(self, process_manager: ProcessManager, log_callback=None):
        self.process_manager = process_manager
        self.log_action = log_callback if log_callback else self._dummy_log
        self.program_directory = self._auto_detect_root_directory()
        self.selected_xlsx_file = None
    
    def _dummy_log(self, message):
        """Временная функция логирования для случаев, когда logger еще не инициализирован"""
        print(f"[LOG] {message}")
    
    def set_log_callback(self, log_callback):
        """Устанавливает функцию логирования после инициализации UI"""
        self.log_action = log_callback
    
    def _auto_detect_root_directory(self):
        """Автоматическое определение корневого каталога программы"""
        try:
            # Для .exe файла определяем каталог по расположению исполняемого файла
            if getattr(sys, 'frozen', False):
                # Если запущен как .exe файл (PyInstaller)
                current_dir = os.path.dirname(sys.executable)
                self.log_action(f"Запуск из .exe файла, каталог: {current_dir}")
            else:
                # Если запущен как Python скрипт
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self.log_action(f"Запуск из Python скрипта, каталог: {current_dir}")
            
            # Проверяем, что мы находимся в правильном каталоге (ищем ключевые файлы/каталоги)
            required_dirs = ['gear_xls', 'xlsx_initial', 'visualiser']
            
            # Сначала проверяем наличие основных каталогов
            missing_dirs = []
            for dir_name in required_dirs:
                dir_path = os.path.join(current_dir, dir_name)
                if not os.path.exists(dir_path):
                    missing_dirs.append(dir_name)
            
            if missing_dirs:
                self.log_action(f"Предупреждение: не найдены каталоги: {', '.join(missing_dirs)}")
                self.log_action(f"Проверяем альтернативные пути...")
                
                # Пробуем найти каталоги в родительских папках (на случай если .exe в подпапке)
                parent_dir = os.path.dirname(current_dir)
                parent_missing = []
                for dir_name in required_dirs:
                    if not os.path.exists(os.path.join(parent_dir, dir_name)):
                        parent_missing.append(dir_name)
                
                if len(parent_missing) < len(missing_dirs):
                    current_dir = parent_dir
                    self.log_action(f"Использую родительский каталог: {current_dir}")
                else:
                    # Создаем недостающие каталоги, если их нет
                    for dir_name in missing_dirs:
                        try:
                            os.makedirs(os.path.join(current_dir, dir_name), exist_ok=True)
                            self.log_action(f"Создан каталог: {dir_name}")
                        except Exception as e:
                            self.log_action(f"Не удалось создать каталог {dir_name}: {e}")
            
            # Создаем обязательные подкаталоги, если их нет
            essential_subdirs = [
                'gear_xls/excel_exports',
                'xlsx_initial'
            ]
            
            for subdir in essential_subdirs:
                subdir_path = os.path.join(current_dir, subdir)
                if not os.path.exists(subdir_path):
                    try:
                        os.makedirs(subdir_path, exist_ok=True)
                        self.log_action(f"Создан подкаталог: {subdir}")
                    except Exception as e:
                        self.log_action(f"Не удалось создать подкаталог {subdir}: {e}")
            
            self.log_action(f"Рабочий каталог определен: {current_dir}")
            return current_dir
            
        except Exception as e:
            self.log_action(f"Ошибка при автоматическом определении каталога: {e}")
            # В случае ошибки возвращаем каталог исполняемого файла
            try:
                if getattr(sys, 'frozen', False):
                    fallback_dir = os.path.dirname(sys.executable)
                else:
                    fallback_dir = os.getcwd()
                self.log_action(f"Использую резервный каталог: {fallback_dir}")
                return fallback_dir
            except:
                return None
    
    def _find_latest_xlsx_file(self):
        """Находит самый новый .xlsx файл в каталоге gear_xls/excel_exports/"""
        if not self.program_directory:
            return None
        
        exports_dir = FileManager.get_file_path(self.program_directory, "gear_xls", "excel_exports")
        if not os.path.exists(exports_dir):
            self.log_action(f"Каталог excel_exports не найден: {exports_dir}")
            return None
        
        # Ищем все .xlsx файлы в каталоге
        xlsx_pattern = os.path.join(exports_dir, "*.xlsx")
        xlsx_files = glob.glob(xlsx_pattern)
        
        if not xlsx_files:
            self.log_action("В каталоге excel_exports не найдено .xlsx файлов")
            return None
        
        # Находим самый новый файл по времени модификации
        latest_file = max(xlsx_files, key=os.path.getmtime)
        self.log_action(f"Найден самый новый .xlsx файл: {os.path.basename(latest_file)}")
        return latest_file
    
    def _convert_xlsx_to_xlsm_with_macro(self, xlsx_file):
        """Конвертирует .xlsx в .xlsm и добавляет VBA модуль"""
        try:
            # Получаем пути
            base_name = os.path.splitext(os.path.basename(xlsx_file))[0]
            output_dir = os.path.dirname(xlsx_file)
            xlsm_file = os.path.join(output_dir, f"{base_name}.xlsm")
            
            # Путь к VBA модулю
            module_path = FileManager.get_file_path(self.program_directory, "gear_xls", "Modul1.bas")
            if not os.path.exists(module_path):
                self.log_action(f"Файл VBA модуля не найден: {module_path}")
                return None
            
            self.log_action("Инициализация COM для Excel...")
            pythoncom.CoInitialize()
            
            try:
                # Создаем объект Excel
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                
                # Открываем исходную книгу
                self.log_action(f"Открытие файла: {os.path.basename(xlsx_file)}")
                wb = excel.Workbooks.Open(xlsx_file)
                
                # Сохраняем как XLSM
                self.log_action(f"Сохранение как XLSM: {os.path.basename(xlsm_file)}")
                wb.SaveAs(xlsm_file, FileFormat=52)  # 52 = xlOpenXMLWorkbookMacroEnabled
                
                # Импорт VBA модуля
                self.log_action("Импорт VBA модуля...")
                vba_project = wb.VBProject
                vba_project.VBComponents.Import(module_path)
                
                # Сохраняем изменения
                wb.Save()
                
                # Закрываем книгу и Excel
                wb.Close(SaveChanges=False)
                excel.Quit()
                
                self.log_action(f"Конвертация завершена: {os.path.basename(xlsm_file)}")
                return xlsm_file
                
            except Exception as e:
                self.log_action(f"Ошибка при работе с Excel: {e}")
                try:
                    excel.Quit()
                except:
                    pass
                return None
                
            finally:
                pythoncom.CoUninitialize()
                
        except Exception as e:
            self.log_action(f"Ошибка при конвертации: {e}")
            return None
    
    def _create_newpref_from_latest_excel(self):
        """Общий метод для создания newpref.xlsx из самого нового Excel файла
        
        Returns:
            str: Путь к созданному newpref.xlsx или None в случае ошибки
        """
        try:
            # Шаг 1: Находим самый новый .xlsx файл
            self.log_action("Шаг 1: Поиск самого нового .xlsx файла...")
            latest_xlsx = self._find_latest_xlsx_file()
            if not latest_xlsx:
                messagebox.showerror("Ошибка", "Не найдено .xlsx файлов в каталоге gear_xls/excel_exports/")
                return None
            
            # Шаг 2: Конвертируем в .xlsm с VBA модулем
            self.log_action("Шаг 2: Конвертация в .xlsm с VBA модулем...")
            xlsm_file = self._convert_xlsx_to_xlsm_with_macro(latest_xlsx)
            if not xlsm_file:
                messagebox.showerror("Ошибка", "Не удалось конвертировать файл в .xlsm")
                return None
            
            # Шаг 3: Запускаем макрос CreateSchedulePlanning
            self.log_action("Шаг 3: Запуск макроса CreateSchedulePlanning...")
            if not self._run_excel_macro(xlsm_file):
                messagebox.showerror("Ошибка", "Не удалось выполнить макрос CreateSchedulePlanning")
                return None
            
            # Шаг 4: Проверяем, что создался newpref.xlsx
            newpref_path = FileManager.get_file_path(self.program_directory, "xlsx_initial", "newpref.xlsx")
            if not os.path.exists(newpref_path):
                messagebox.showerror("Ошибка", f"Файл newpref.xlsx не был создан по пути: {newpref_path}")
                return None
            
            self.log_action("Файл newpref.xlsx успешно создан!")
            return newpref_path
            
        except Exception as e:
            self.log_action(f"Ошибка при создании newpref.xlsx: {e}")
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
            return None

    def _run_excel_macro(self, xlsm_file, macro_name="CreateSchedulePlanning"):
        """Запускает макрос в Excel файле"""
        try:
            self.log_action(f"Запуск макроса {macro_name}...")
            pythoncom.CoInitialize()
            
            try:
                # Создаем объект Excel
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                
                # Открываем XLSM файл
                wb = excel.Workbooks.Open(xlsm_file)
                
                # Запускаем макрос
                excel.Application.Run(macro_name)
                
                # Сохраняем изменения
                wb.Save()
                
                # Закрываем книгу и Excel
                wb.Close(SaveChanges=False)
                excel.Quit()
                
                self.log_action(f"Макрос {macro_name} успешно выполнен")
                return True
                
            except Exception as e:
                self.log_action(f"Ошибка при выполнении макроса: {e}")
                try:
                    excel.Quit()
                except:
                    pass
                return False
                
            finally:
                pythoncom.CoUninitialize()
                
        except Exception as e:
            self.log_action(f"Ошибка при запуске макроса: {e}")
            return False

    def get_program_directory(self):
        """Возвращает текущий рабочий каталог"""
        return self.program_directory

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
        """Обработчик для кнопки 7.0: Сложная логика создания и открытия newpref.xlsx"""
        if not self._check_directory():
            return
        
        self.log_action("Начинаем процесс создания newpref.xlsx...")
        
        def process_in_thread():
            try:
                # Выполняем общую последовательность шагов а, б, в
                newpref_path = self._create_newpref_from_latest_excel()
                if not newpref_path:
                    return  # Ошибка уже отображена в _create_newpref_from_latest_excel
                
                # Шаг 5: Открываем созданный файл
                self.log_action("Шаг 4: Открытие созданного newpref.xlsx...")
                if FileManager.open_file(newpref_path, "newpref.xlsx"):
                    self.log_action("Процесс успешно завершен! Файл newpref.xlsx открыт.")
                    messagebox.showinfo("Успех", "Файл newpref.xlsx успешно создан и открыт!")
                else:
                    messagebox.showerror("Ошибка", "Не удалось открыть созданный файл newpref.xlsx")
                    
            except Exception as e:
                self.log_action(f"Ошибка в процессе создания newpref.xlsx: {e}")
                messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
        
        # Запускаем в отдельном потоке, чтобы не блокировать интерфейс
        threading.Thread(target=process_in_thread, daemon=True).start()
    
    def run_scheduler_newpref(self):
        """Обработчик для кнопки 7: Создание newpref.xlsx и запуск планировщика"""
        if not self._check_directory():
            return
        
        self.log_action("Начинаем процесс создания newpref.xlsx и запуска планировщика...")
        
        def process_in_thread():
            try:
                # Выполняем общую последовательность шагов а, б, в
                newpref_path = self._create_newpref_from_latest_excel()
                if not newpref_path:
                    return  # Ошибка уже отображена в _create_newpref_from_latest_excel
                
                # Шаг 5: Запускаем планировщик с newpref.xlsx
                self.log_action("Шаг 4: Запуск планировщика с newpref.xlsx...")
                
                commands = [
                    "python main_sch.py xlsx_initial/newpref.xlsx --time-limit 300 --verbose --time-interval 5"
                ]
                
                # Запускаем планировщик в отдельном процессе
                self.process_manager.terminal_process = self.process_manager.execute_in_terminal(
                    commands, self.program_directory)
                
                self.log_action("Процесс успешно завершен! Планировщик запущен с новым newpref.xlsx.")
                messagebox.showinfo("Успех", "Файл newpref.xlsx создан и планировщик запущен!")
                    
            except Exception as e:
                self.log_action(f"Ошибка в процессе создания newpref.xlsx и запуска планировщика: {e}")
                messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
        
        # Запускаем в отдельном потоке, чтобы не блокировать интерфейс
        threading.Thread(target=process_in_thread, daemon=True).start()
    
    def _check_directory(self):
        """Проверка установки рабочего каталога"""
        if not self.program_directory:
            messagebox.showwarning("Предупреждение", "Сначала выберите рабочий каталог программы")
            return False
        return True
