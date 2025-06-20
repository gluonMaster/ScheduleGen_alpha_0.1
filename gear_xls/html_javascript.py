"""
Модуль для генерации JavaScript-кода для интерактивной работы с HTML-расписанием.
Использует модульный подход для организации кода.
"""
import os

def get_javascript(cellHeight, dayCellWidth, headerHeight, days_order, time_interval, borderWidth=1):
    """
    Возвращает строку с JavaScript-кодом для интерактивности HTML-расписания.
    
    Args:
        cellHeight (int): Высота ячейки в пикселях
        dayCellWidth (int): Ширина ячейки дня в пикселях
        headerHeight (float): Высота заголовка в пикселях
        days_order (list): Список дней недели
        time_interval (int): Интервал времени в минутах
        borderWidth (int): Толщина границы ячейки в пикселях
        
    Returns:
        str: JavaScript-код
    """
    # Путь к директории с JS модулями
    js_dir = os.path.join(os.path.dirname(__file__), 'js_modules')
    
    # Формируем словарь с переменными для подстановки в JS
    variables = {
        'gridCellHeight': cellHeight,
        'dayCellWidth': dayCellWidth,
        'headerHeight': headerHeight,
        'daysOrder': str(days_order),
        'timeInterval': time_interval,
        'borderWidth': float(borderWidth)
    }
    
    # Инициализация JavaScript с переменными
    js_variables = f"""
        var gridCellHeight = {cellHeight};
        var dayCellWidth = {dayCellWidth};
        var headerHeight = {headerHeight};
        var daysOrder = {str(days_order)};
        var timeInterval = {time_interval};
        var borderWidth = {float(borderWidth)};

        // Глобальные переменные для отслеживания состояния
        window.editDialogOpen = false;
        window.draggedBlock = null;
        
        // Переменные для хранения параметров компенсации
        window.compensationFactor = 0.4;
        window.compensationExponent = 1.02;
        window.previousCompensationFactor = 0.4;
        window.previousCompensationExponent = 1.02;        // Храним измеренную ширину колонки времени
        var measuredTimeColWidth = 0;
    """
    
    # Список названий модулей для загрузки (обновленный порядок)
    # ВАЖНО: services должны загружаться первыми, так как используются другими модулями
    base_module_names = [
        'services/building_service',      # НОВЫЙ СЕРВИС - загружается первым
        'services/drag_drop_service',     # НОВЫЙ СЕРВИС для drag&drop функциональности
        'services/grid_snap_service',     # НОВЫЙ СЕРВИС для привязки к сетке
        'services/block_drop_service',    # НОВЫЙ СЕРВИС для обработки завершения перетаскивания
        'core',
        'position',
        'drag_drop_refactored',           # Обновленный модуль drag_drop
        'settings_panel',
        'save_export',
        'column_helpers',  # Модуль для работы с колонками в разных зданиях
        'color_utils',     # Модуль для работы с цветами
        'adaptive_text_color',  # Модуль для адаптивного изменения цвета текста
        'export_to_excel'  # Модуль для экспорта расписания в Excel
    ]
    
    # Список названий модулей для добавления блоков
    add_blocks_module_names = [
        'add_blocks_main',
        'block_creation_dialog',
        'block_positioning',
        'block_event_handlers',
        'quick_add_mode',
        'block_utils',
        'editing_update',  # Обновленный модуль редактирования с поддержкой зданий
        'delete_blocks',     # Модуль для удаления блоков
        'delete_blocks_observer'  # Наблюдатель за новыми блоками для режима удаления
    ]
    
    # Загружаем содержимое модулей
    js_modules = {}
    
    # Загружаем содержимое базовых модулей
    for module_name in base_module_names:
        # Обрабатываем путь для модулей в подпапках (например, services/building_service)
        if '/' in module_name:
            module_path = os.path.join(js_dir, f"{module_name}.js")
        else:
            module_path = os.path.join(js_dir, f"{module_name}.js")
            
        try:
            with open(module_path, 'r', encoding='utf-8') as f:
                js_modules[module_name] = f.read()
                print(f"Loaded JS module: {module_name}")  # Для отладки
        except FileNotFoundError:
            # Если файл не найден, добавляем заглушку с предупреждением
            js_modules[module_name] = f"// ВНИМАНИЕ: Модуль {module_name}.js не найден по пути {module_path}"
            print(f"WARNING: JS module not found: {module_path}")
    
    # Загружаем содержимое модулей добавления блоков
    for module_name in add_blocks_module_names:
        module_path = os.path.join(js_dir, f"{module_name}.js")
        try:
            with open(module_path, 'r', encoding='utf-8') as f:
                js_modules[module_name] = f.read()
                print(f"Loaded JS module: {module_name}")  # Для отладки
        except FileNotFoundError:
            # Если файл не найден, добавляем заглушку
            js_modules[module_name] = f"// ВНИМАНИЕ: Модуль {module_name}.js не найден по пути {module_path}"
            print(f"WARNING: JS module not found: {module_path}")
    
    # Формируем полный JavaScript-код
    full_js = f"""
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            {js_variables}
              // === НОВЫЕ СЕРВИСЫ ДЛЯ DRAG&DROP ФУНКЦИОНАЛЬНОСТИ ===
            {js_modules.get('services/building_service', '')}
            
            {js_modules.get('services/drag_drop_service', '')}
            
            {js_modules.get('services/grid_snap_service', '')}
            
            {js_modules.get('services/block_drop_service', '')}
            
            // Подключение основных модулей
            {js_modules.get('core', '')}
            
            {js_modules.get('position', '')}
            
            {js_modules.get('drag_drop_refactored', '')}
            
            {js_modules.get('column_helpers', '')}
            
            {js_modules.get('settings_panel', '')}
            
            {js_modules.get('save_export', '')}
            
            // Подключение модулей для работы с цветами
            {js_modules.get('color_utils', '')}
            
            {js_modules.get('adaptive_text_color', '')}
            
            // Подключение модуля экспорта в Excel
            {js_modules.get('export_to_excel', '')}
            
            // Подключение модулей для работы с блоками
            {js_modules.get('block_utils', '')}
            
            {js_modules.get('block_positioning', '')}
            
            {js_modules.get('block_event_handlers', '')}
            
            {js_modules.get('block_creation_dialog', '')}
            
            {js_modules.get('quick_add_mode', '')}
            
            {js_modules.get('add_blocks_main', '')}
            
            // Подключение обновленного модуля редактирования с поддержкой зданий
            {js_modules.get('editing_update', '')}
            
            // Подключение модулей для удаления блоков
            {js_modules.get('delete_blocks', '')}
            
            {js_modules.get('delete_blocks_observer', '')}            // Инициализация элементов только если страница не является финальной
            if (!document.body.classList.contains('static-schedule')) {{
                // Инициализация новых сервисов
                if (typeof DragDropService !== 'undefined') {{
                    console.log('Initializing DragDropService...');
                }}
                if (typeof GridSnapService !== 'undefined') {{
                    console.log('GridSnapService loaded successfully');
                }}
                if (typeof BlockDropService !== 'undefined') {{
                    console.log('BlockDropService loaded successfully');
                }}
                
                initDragAndDrop();
                initBlockEditing();
                initCompensationSettings();
                initSaveExport();
                initAddBlocks();  // Инициализация нового модуля
                initDeleteBlocks(); // Инициализация модуля удаления блоков
                initDeleteBlocksObserver(); // Инициализация наблюдателя за блоками
                initAdaptiveTextColor(); // Инициализация адаптивного цвета текста
                initExcelExport(); // Инициализация функции экспорта в Excel
            }}
            
            // Первоначальное позиционирование
            updateActivityPositions();
              // Инициализация всех сервисов
            if (typeof BuildingService !== 'undefined') {{
                console.log('BuildingService initialized successfully');
                console.log('Available buildings:', BuildingService.getAvailableBuildings());
            }} else {{
                console.error('BuildingService failed to load');
            }}
            
            // Проверяем инициализацию новых drag&drop сервисов
            if (typeof DragDropService !== 'undefined') {{
                console.log('DragDropService initialized successfully');
            }} else {{
                console.warn('DragDropService not available, using legacy implementation');
            }}
            
            if (typeof GridSnapService !== 'undefined') {{
                console.log('GridSnapService initialized successfully');  
            }} else {{
                console.warn('GridSnapService not available, using legacy implementation');
            }}
            
            if (typeof BlockDropService !== 'undefined') {{
                console.log('BlockDropService initialized successfully');
            }} else {{
                console.warn('BlockDropService not available, using legacy implementation');
            }}
        }});
        
        // Функции для сохранения и загрузки настроек
        function saveSettings(settings) {{
            try {{
                localStorage.setItem('scheduleCompensationSettings', JSON.stringify(settings));
            }} catch (e) {{
                console.error('Не удалось сохранить настройки:', e);
            }}
        }}
        
        function loadSettings() {{
            try {{
                var settings = localStorage.getItem('scheduleCompensationSettings');
                return settings ? JSON.parse(settings) : null;
            }} catch (e) {{
                console.error('Не удалось загрузить настройки:', e);
                return null;
            }}
        }}
    </script>"""
    
    return full_js
