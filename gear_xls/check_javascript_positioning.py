#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка JavaScript модулей, которые могут влиять на позиционирование блоков.
"""

import os
import re

def analyze_javascript_modules():
    """Анализирует JavaScript модули на предмет логики позиционирования."""
    print("🔍 АНАЛИЗ JAVASCRIPT МОДУЛЕЙ")
    print("=" * 50)
    
    js_modules_dir = "js_modules"
    if not os.path.exists(js_modules_dir):
        print(f"❌ Директория {js_modules_dir} не найдена")
        return
    
    # Модули, которые могут влиять на позиционирование
    positioning_modules = [
        'position.js',
        'drag_drop.js', 
        'core.js',
        'block_positioning.js'
    ]
    
    found_issues = []
    
    for module_name in positioning_modules:
        module_path = os.path.join(js_modules_dir, module_name)
        
        if os.path.exists(module_path):
            print(f"\n📄 Анализ {module_name}:")
            with open(module_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ищем функции позиционирования
            positioning_functions = re.findall(r'function\s+(\w*[Pp]osition\w*)', content)
            if positioning_functions:
                print(f"  Функции позиционирования: {positioning_functions}")
            
            # Ищем updateActivityPositions
            if 'updateActivityPositions' in content:
                print(f"  ✅ Содержит updateActivityPositions")
                
                # Извлекаем функцию
                update_match = re.search(r'function updateActivityPositions.*?(?=\n\s*function|\n\s*$)', content, re.DOTALL)
                if update_match:
                    func_content = update_match.group(0)
                    print(f"  Длина функции: {len(func_content)} символов")
                    
                    # Ищем потенциальные проблемы
                    if 'left:' in func_content or 'style.left' in func_content:
                        print(f"  ⚠️  ВНИМАНИЕ: Функция изменяет left позиционирование!")
                        found_issues.append(f"{module_name}: изменяет left позиционирование")
            
            # Ищем обработчики DOMContentLoaded
            if 'DOMContentLoaded' in content:
                print(f"  📋 Имеет обработчик DOMContentLoaded")
                
                # Проверяем что вызывается при загрузке
                dom_match = re.search(r"addEventListener\s*\(\s*['\"]DOMContentLoaded['\"].*?\}\s*\)", content, re.DOTALL)
                if dom_match:
                    dom_content = dom_match.group(0)
                    if 'updateActivityPositions' in dom_content:
                        print(f"  ⚠️  updateActivityPositions вызывается при загрузке!")
                        found_issues.append(f"{module_name}: updateActivityPositions при загрузке")
            
            # Ищем компенсационные факторы
            compensation_patterns = [
                r'compensationFactor',
                r'compensationExponent', 
                r'borderWidth.*compensation',
                r'gridCellHeight.*compensation'
            ]
            
            for pattern in compensation_patterns:
                if re.search(pattern, content):
                    print(f"  🔧 Найден паттерн компенсации: {pattern}")
                    found_issues.append(f"{module_name}: использует компенсацию - {pattern}")
        
        else:
            print(f"❌ {module_name} не найден")
    
    # Результат анализа
    print(f"\n📊 РЕЗУЛЬТАТ АНАЛИЗА:")
    if found_issues:
        print(f"❌ Найдены потенциальные проблемы:")
        for issue in found_issues:
            print(f"  - {issue}")
    else:
        print(f"✅ Критических проблем не найдено")
    
    return found_issues

def check_html_javascript_generation():
    """Проверяет генерацию JavaScript в HTML."""
    print(f"\n🔍 ПРОВЕРКА ГЕНЕРАЦИИ JAVASCRIPT")
    print("=" * 50)
    
    try:
        from html_javascript import get_javascript
        
        # Параметры как в реальном использовании
        cellHeight = 15
        dayCellWidth = 100  
        headerHeight = 45
        days_order = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"]
        time_interval = 5
        borderWidth = 0.5
        
        js_code = get_javascript(cellHeight, dayCellWidth, headerHeight, days_order, time_interval, borderWidth)
        
        print(f"Размер сгенерированного JavaScript: {len(js_code)} символов")
        
        # Проверяем переменные
        variables_to_check = [
            ('gridCellHeight', str(cellHeight)),
            ('dayCellWidth', str(dayCellWidth)),
            ('headerHeight', str(headerHeight)),
            ('timeInterval', str(time_interval)),
            ('borderWidth', str(borderWidth))
        ]
        
        for var_name, expected_value in variables_to_check:
            pattern = f'var {var_name} = {expected_value}'
            if pattern in js_code:
                print(f"  ✅ {var_name} = {expected_value}")
            else:
                print(f"  ❌ {var_name} не найден или неправильное значение")
                
                # Ищем что там на самом деле
                actual_match = re.search(f'var {var_name} = ([^;]+)', js_code)
                if actual_match:
                    actual_value = actual_match.group(1)
                    print(f"    Фактическое значение: {actual_value}")
        
        # Ищем функции инициализации
        init_functions = [
            'initDragAndDrop',
            'updateActivityPositions',
            'initBlockEditing'
        ]
        
        for func_name in init_functions:
            if func_name in js_code:
                print(f"  ✅ {func_name}() вызывается")
            else:
                print(f"  ❌ {func_name}() не найден")
    
    except Exception as e:
        print(f"❌ Ошибка при проверке JavaScript: {e}")

def create_minimal_test_html():
    """Создает минимальный HTML для тестирования позиционирования."""
    print(f"\n🔍 СОЗДАНИЕ МИНИМАЛЬНОГО ТЕСТА")
    print("=" * 50)
    
    # Минимальный HTML с одним блоком
    html_content = """<!DOCTYPE html>
<html lang='ru'>
<head>
    <meta charset="UTF-8">
    <style>
        .schedule-container { position: relative; width: 500px; border: 2px solid red; }
        .schedule-grid { border-collapse: collapse; }
        .schedule-grid th, .schedule-grid td { 
            border: 1px solid #ddd; 
            width: 100px; height: 15px; 
            text-align: center; 
        }
        .time-cell { width: 80px; background: #f0f0f0; }
        .activity-block { 
            position: absolute; 
            background: #FFD700; 
            border: 1px solid #000;
            padding: 2px;
            font-size: 10px;
        }
    </style>
</head>
<body>
    <h1>Тест позиционирования</h1>
    <div class="schedule-container">
        <table class="schedule-grid">
            <thead>
                <tr>
                    <th class="time-cell">Время</th>
                    <th class="day-Mo">Mo<br>.01</th>
                    <th class="day-Mo">Mo<br>.02</th>
                </tr>
            </thead>
            <tbody>
                <tr><td class="time-cell">09:00</td><td></td><td></td></tr>
                <tr><td class="time-cell"></td><td></td><td></td></tr>
                <tr><td class="time-cell"></td><td></td><td></td></tr>
            </tbody>
        </table>
        
        <!-- Блок должен быть на позиции left: 80px (после колонки времени) -->
        <div class='activity-block' style='top:45px; left:80px; width:100px; height:45px;'>
            Тест 1<br>col=0
        </div>
        
        <!-- Блок должен быть на позиции left: 180px (после первого столбца) -->
        <div class='activity-block' style='top:45px; left:180px; width:100px; height:45px;'>
            Тест 2<br>col=1  
        </div>
    </div>
    
    <p>Красная рамка - граница контейнера</p>
    <p>Блок 1 (желтый) должен быть в первой колонке</p>
    <p>Блок 2 (желтый) должен быть во второй колонке</p>
</body>
</html>"""
    
    # Сохраняем тестовый файл
    test_file = "test_positioning.html"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Создан тестовый файл: {test_file}")
    print(f"Откройте его в браузере и проверьте позиционирование")
    
    return test_file

def main():
    """Основная функция проверки JavaScript."""
    issues = analyze_javascript_modules()
    check_html_javascript_generation()
    test_file = create_minimal_test_html()
    
    print(f"\n" + "=" * 60)
    print(f"💡 ВЫВОДЫ:")
    
    if issues:
        print(f"❌ Найдены проблемы в JavaScript:")
        for issue in issues:
            print(f"  - {issue}")
        print(f"\n🔧 РЕКОМЕНДАЦИИ:")
        print(f"1. Проверьте updateActivityPositions() - возможно он перемещает блоки")
        print(f"2. Отключите компенсационные факторы временно")
        print(f"3. Проверьте что JavaScript не изменяет изначальные позиции")
    else:
        print(f"✅ JavaScript модули выглядят нормально")
        print(f"🔧 Проблема может быть в:")
        print(f"1. CSS стилях")
        print(f"2. Структуре данных") 
        print(f"3. Другой логике позиционирования")
    
    print(f"\n📋 ДАЛЬНЕЙШИЕ ШАГИ:")
    print(f"1. Откройте {test_file} в браузере")
    print(f"2. Запустите debug_main.py для сравнения с main.py")
    print(f"3. Проверьте консоль браузера на ошибки JavaScript")

if __name__ == "__main__":
    main()
    