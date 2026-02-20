"""
Пример использования улучшенного визуализатора расписания
Версия 3: исправлено позиционирование текста в блоках, отключена генерация индивидуальных расписаний
"""

import os
import sys
from schedule_visualizer_enhanced import main
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# регистрируем жирный шрифт один раз при старте
try:
    pdfmetrics.registerFont(TTFont('Arial-Bold', 'c:\\Windows\\Fonts\\arialbd.ttf'))
except:
    # Если жирный шрифт недоступен, продолжаем без него
    pass

if __name__ == "__main__":
    # Путь к Excel-файлу с расписанием
    excel_file = "optimized_schedule.xlsx"
    
    # Проверяем наличие файла
    if not os.path.exists(excel_file):
        print(f"Ошибка: Файл {excel_file} не найден.")
        print("Пожалуйста, убедитесь, что файл с расписанием находится в текущей директории.")
        sys.exit(1)
    
    # Путь для сохранения PDF-файла
    pdf_file = "enhanced_schedule_visualization_v3.pdf"
    
    try:
        # Генерируем визуализацию расписания с исправлениями версии 3
        main(excel_file, pdf_file, export_html=True)
        
        print(f"\nРасписание успешно визуализировано с исправлениями версии 3:")
        print(f"1. Основное расписание: {pdf_file}")
        print(f"   - Рабочие дни (Mo-Fr): холст 2325×2171 пикселей")
        print(f"   - Выходные дни (Sa): холст A4")
        print(f"2. HTML-версия: {os.path.splitext(pdf_file)[0] + '.html'}")
        
        print("\nИсправления в версии 3:")
        print("- ИСПРАВЛЕНО: Правильное вертикальное позиционирование текста в блоках")
        print("- Текст теперь центрирован по вертикали с учетом разных размеров шрифтов")
        print("- Отключена генерация индивидуальных расписаний учителей и групп")
        print("- Оставлен только сводное расписание и HTML-экспорт")
        print("- Минимизированы все поля для максимального использования пространства")
        print("- Размер шрифта для рабочих дней увеличен на 30%")
        print("- Размер шрифта для субботы уменьшен в 2 раза от рабочих дней")
        
    except Exception as e:
        print(f"Ошибка при создании визуализации: {e}")
        import traceback
        traceback.print_exc()