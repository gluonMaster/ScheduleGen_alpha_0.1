import time
import tkinter as tk


class Logger:
    """Система логирования для GUI"""
    
    def __init__(self, log_text_widget, status_bar_widget, root_widget):
        self.log_text = log_text_widget
        self.status_bar = status_bar_widget
        self.root = root_widget
    
    def log_action(self, message):
        """Добавляет сообщение в лог и обновляет статус"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)  # Прокрутка до конца
        self.status_bar.config(text=message)
        self.root.update()
    
    def clear_log(self):
        """Очистка лога"""
        self.log_text.delete(1.0, tk.END)
    
    def set_status(self, message):
        """Установка статуса без записи в лог"""
        self.status_bar.config(text=message)
