// Основной модуль для создания новых блоков занятий в расписании

// Импорт субмодулей (в реальной среде они подключаются через механизм импорта)
// В контексте HTML эти файлы нужно будет просто подключить через отдельные теги <script>

// Функция инициализации создания новых блоков
function initAddBlocks() {
    // Добавляем кнопку создания нового блока
    addCreateBlockButton();
}

// Функция для добавления кнопки создания нового блока
function addCreateBlockButton() {
    // Создаем кнопки
    var createButton = document.createElement('button');
    createButton.id = 'create-block-button';
    createButton.innerHTML = '+';
    createButton.className = 'create-block-button';
    
    var toggleModeButton = document.createElement('button');
    toggleModeButton.id = 'toggle-add-mode';
    toggleModeButton.innerHTML = '🔧';  // Символ гаечного ключа
    toggleModeButton.className = 'toggle-add-mode-button';
    
    // Находим блок с липкими кнопками
    var stickyButtons = document.querySelector('.sticky-buttons');
    if (stickyButtons) {
        // Добавляем кнопки в блок sticky-buttons
        stickyButtons.appendChild(createButton);
        stickyButtons.appendChild(toggleModeButton);
    } else {
        // Если не нашли блок sticky-buttons, создаем его
        stickyButtons = document.createElement('div');
        stickyButtons.className = 'sticky-buttons';
        stickyButtons.appendChild(createButton);
        stickyButtons.appendChild(toggleModeButton);
        
        // Добавляем перед первым контейнером расписания
        var firstContainer = document.querySelector('.schedule-container');
        if (firstContainer) {
            firstContainer.parentNode.insertBefore(stickyButtons, firstContainer);
        } else {
            document.body.insertBefore(stickyButtons, document.body.firstChild);
        }
    }
    
    // Стили для кнопок
    var style = document.createElement('style');
    style.textContent = `
        .create-block-button {
            padding: 8px 16px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            margin: 5px;
            transition: background-color 0.3s;
        }
        .create-block-button:hover {
            background-color: #45a049;
        }
        .toggle-add-mode-button {
            padding: 8px 16px;
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            margin: 5px;
            transition: background-color 0.3s;
        }
        .toggle-add-mode-button.active {
            background-color: #FF5722;
        }
        .toggle-add-mode-button:hover {
            opacity: 0.9;
        }
        .cell-highlight {
            background-color: rgba(76, 175, 80, 0.2) !important;
            cursor: pointer !important;
        }
        .cell-highlight:hover {
            background-color: rgba(76, 175, 80, 0.4) !important;
        }
    `;
    document.head.appendChild(style);
    
    // Обработчик события для кнопки создания
    createButton.addEventListener('click', openCreateBlockDialog);
    
    // Обработчик для режима добавления
    initQuickAddByClick(toggleModeButton);
    
    // Удаляем блок schedule-controls, если он существует
    var scheduleControls = document.querySelector('.schedule-controls');
    if (scheduleControls) {
        scheduleControls.parentNode.removeChild(scheduleControls);
    }
}

// Экспортируем функцию инициализации
window.initAddBlocks = initAddBlocks;