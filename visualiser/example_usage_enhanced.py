"""
Пример использования улучшенного визуализатора расписания
"""

import os
import sys
from schedule_visualizer_enhanced import main
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# регистрируем жирный шрифт один раз при старте
pdfmetrics.registerFont(TTFont('Arial-Bold', 'c:\\Windows\\Fonts\\arialbd.ttf'))

if __name__ == "__main__":
    # Путь к Excel-файлу с расписанием
    excel_file = "optimized_schedule.xlsx"
    
    # Проверяем наличие файла
    if not os.path.exists(excel_file):
        print(f"Ошибка: Файл {excel_file} не найден.")
        print("Пожалуйста, убедитесь, что файл с расписанием находится в текущей директории.")
        sys.exit(1)
    
    # Путь для сохранения PDF-файла
    pdf_file = "enhanced_schedule_visualization.pdf"
    
    try:
        # Генерируем визуализацию расписания с улучшениями
        main(excel_file, pdf_file, export_teachers=True, export_groups=True, export_html=True)
        
        print(f"\nРасписание успешно визуализировано с улучшениями:")
        print(f"1. Основное расписание: {pdf_file}")
        print(f"2. HTML-версия: {os.path.splitext(pdf_file)[0] + '.html'}")
        print(f"3. Расписания преподавателей: папка 'teacher_schedules/'")
        print(f"4. Расписания групп: папка 'group_schedules/'")
        
        print("\nУлучшения включают:")
        print("- Блоки со скругленными углами")
        print("- Адаптивный HTML с поддержкой мобильных устройств")
        print("- Темная тема и возможность поиска в HTML-версии")
        print("- Отдельные PDF-файлы для каждого преподавателя и группы")
        
    except Exception as e:
        print(f"Ошибка при создании визуализации: {e}")
        import traceback
        traceback.print_exc()
