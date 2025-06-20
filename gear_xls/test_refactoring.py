#!/usr/bin/env python3
"""
Тестовый скрипт для проверки загрузки JavaScript модулей после рефакторинга.
Проверяет, что все новые сервисы корректно загружаются и интегрируются.
"""

import os
import sys

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from html_javascript import get_javascript
    print("✅ Модуль html_javascript успешно импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта html_javascript: {e}")
    sys.exit(1)

def test_javascript_generation():
    """Тестирует генерацию JavaScript кода с новыми сервисами"""
    
    # Параметры для тестирования
    test_params = {
        'cellHeight': 40,
        'dayCellWidth': 120, 
        'headerHeight': 50,
        'days_order': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        'time_interval': 30,
        'borderWidth': 1
    }
    
    try:
        js_code = get_javascript(**test_params)
        print("✅ JavaScript код успешно сгенерирован")
          # Проверяем наличие новых сервисов в сгенерированном коде
        required_services = [
            'DragDropService',
            'GridSnapService',
            'BlockDropService'
        ]
        
        missing_services = []
        for service in required_services:
            if service not in js_code:
                missing_services.append(service)
        
        if missing_services:
            print(f"⚠️  Отсутствуют следующие сервисы: {missing_services}")
        else:
            print("✅ Все новые сервисы присутствуют в коде")
            
        # Проверяем, что старые функции сохранены для совместимости
        legacy_functions = [
            'initDragAndDrop',
            'processBlockDrop'
        ]
        
        missing_legacy = []
        for func in legacy_functions:
            if func not in js_code:
                missing_legacy.append(func)
                
        if missing_legacy:
            print(f"⚠️  Отсутствуют функции обратной совместимости: {missing_legacy}")
        else:
            print("✅ Функции обратной совместимости сохранены")
            
        # Проверяем корректность инициализации
        init_checks = [
            'initDragAndDrop();',
            'DragDropService',
            'typeof DragDropService !== \'undefined\''
        ]
        
        missing_init = []
        for check in init_checks:
            if check not in js_code:
                missing_init.append(check)
                
        if missing_init:
            print(f"⚠️  Проблемы с инициализацией: {missing_init}")
        else:
            print("✅ Инициализация корректна")
            
        return len(missing_services) == 0 and len(missing_legacy) == 0 and len(missing_init) == 0
        
    except Exception as e:
        print(f"❌ Ошибка при генерации JavaScript: {e}")
        return False

def check_service_files():
    """Проверяет наличие файлов новых сервисов"""
    
    js_dir = os.path.join(os.path.dirname(__file__), 'js_modules')
    services_dir = os.path.join(js_dir, 'services')
    
    required_files = [
        'drag_drop_service.js',
        'grid_snap_service.js', 
        'block_drop_service.js',
        'building_service.js'  # Существующий сервис
    ]
    
    all_present = True
    
    print(f"Проверяем директорию: {services_dir}")
    
    for filename in required_files:
        filepath = os.path.join(services_dir, filename)
        if os.path.exists(filepath):
            # Проверяем размер файла
            size = os.path.getsize(filepath)
            print(f"✅ {filename} найден (размер: {size} байт)")
        else:
            print(f"❌ {filename} не найден")
            all_present = False
            
    # Проверяем основной рефакторенный файл
    refactored_file = os.path.join(js_dir, 'drag_drop_refactored.js')
    if os.path.exists(refactored_file):
        size = os.path.getsize(refactored_file)
        print(f"✅ drag_drop_refactored.js найден (размер: {size} байт)")
    else:
        print(f"❌ drag_drop_refactored.js не найден")
        all_present = False
        
    return all_present

def main():
    """Основная функция тестирования"""
    print("🧪 Запуск тестов рефакторинга drag&drop модулей")
    print("=" * 60)
    
    # Тест 1: Проверка файлов
    print("\n📁 Тест 1: Проверка наличия файлов сервисов")
    files_ok = check_service_files()
    
    # Тест 2: Генерация JavaScript
    print("\n⚙️  Тест 2: Тестирование генерации JavaScript")
    js_ok = test_javascript_generation()
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    
    if files_ok and js_ok:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Рефакторинг drag&drop модулей выполнен корректно")
        print("✅ Обратная совместимость сохранена")
        print("✅ Новые сервисы интегрированы правильно")
        return True
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        if not files_ok:
            print("❌ Проблемы с файлами сервисов")
        if not js_ok:
            print("❌ Проблемы с генерацией JavaScript")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
