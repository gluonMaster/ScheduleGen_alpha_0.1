/**
 * Модуль инициализации приложения
 * Отвечает за инициализацию всех компонентов и сервисов приложения
 */

// Флаг для предотвращения повторной инициализации
window.applicationInitialized = window.applicationInitialized || false;

function initializeApplication() {
    // Проверяем, не была ли уже выполнена инициализация
    if (window.applicationInitialized && !document.body.classList.contains('static-schedule')) {
        console.log('Application already initialized, skipping...');
        return;
    }

    // Инициализация элементов только если страница не является финальной
    if (!document.body.classList.contains('static-schedule')) {
        // Инициализация новых сервисов
        if (typeof DragDropService !== 'undefined') {
            console.log('Initializing DragDropService...');
        }
        if (typeof GridSnapService !== 'undefined') {
            console.log('GridSnapService loaded successfully');
        }
        if (typeof BlockDropService !== 'undefined') {
            console.log('BlockDropService loaded successfully');
        }
        
        initDragAndDrop();
        initBlockEditing();
        initCompensationSettings();
        initSaveExport();
        initAddBlocks();  // Инициализация нового модуля
        initDeleteBlocks(); // Инициализация модуля удаления блоков
        initDeleteBlocksObserver(); // Инициализация наблюдателя за блоками
        initAdaptiveTextColor(); // Инициализация адаптивного цвета текста
        initExcelExport(); // Инициализация функции экспорта в Excel
        
        // Устанавливаем флаг инициализации
        window.applicationInitialized = true;
    }
    
    // Первоначальное позиционирование
    updateActivityPositions();
    
    // Инициализация всех сервисов
    if (typeof BuildingService !== 'undefined') {
        console.log('BuildingService initialized successfully');
        console.log('Available buildings:', BuildingService.getAvailableBuildings());
    } else {
        console.error('BuildingService failed to load');
    }
    
    // Проверяем инициализацию новых drag&drop сервисов
    if (typeof DragDropService !== 'undefined') {
        console.log('DragDropService initialized successfully');
    } else {
        console.warn('DragDropService not available, using legacy implementation');
    }
    
    if (typeof GridSnapService !== 'undefined') {
        console.log('GridSnapService initialized successfully');  
    } else {
        console.warn('GridSnapService not available, using legacy implementation');
    }
    
    if (typeof BlockDropService !== 'undefined') {
        console.log('BlockDropService initialized successfully');
    } else {
        console.warn('BlockDropService not available, using legacy implementation');
    }
}

// Функции для сохранения и загрузки настроек
function saveSettings(settings) {
    try {
        localStorage.setItem('scheduleCompensationSettings', JSON.stringify(settings));
    } catch (e) {
        console.error('Не удалось сохранить настройки:', e);
    }
}

function loadSettings() {
    try {
        var settings = localStorage.getItem('scheduleCompensationSettings');
        return settings ? JSON.parse(settings) : null;
    } catch (e) {
        console.error('Не удалось загрузить настройки:', e);
        return null;
    }
}

// Функция для сброса состояния инициализации (для принудительной переинициализации)
function resetApplicationState() {
    window.applicationInitialized = false;
    console.log('Application state reset. Ready for re-initialization.');
}

// Функция для принудительной переинициализации приложения
function forceReinitializeApplication() {
    resetApplicationState();
    initializeApplication();
}
