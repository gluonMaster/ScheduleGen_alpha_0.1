// Модуль для функционала быстрого добавления блоков по клику на ячейку

// Функция для инициализации быстрого добавления по клику на ячейку
function initQuickAddByClick(addBlockButton) {
    // Режим добавления блоков
    var addBlockMode = false;
    
    // Текущее активное здание
    var activeBuilding = 'Villa';
    
    // Используем переданную кнопку или создаем новую
    if (!addBlockButton) {
        addBlockButton = document.createElement('button');
        addBlockButton.id = 'toggle-add-mode';
        addBlockButton.innerHTML = '🔧';
        addBlockButton.className = 'toggle-add-mode-button';
        
        // Стили для кнопки
        var style = document.createElement('style');
        style.textContent = `
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
        `;
        document.head.appendChild(style);
        
        // Добавляем кнопку в блок .sticky-buttons
        var stickyButtons = document.querySelector('.sticky-buttons');
        if (stickyButtons) {
            stickyButtons.appendChild(addBlockButton);
        }
    }
    
    // Добавляем стиль для индикатора активного здания
    var buildingIndicatorStyle = document.createElement('style');
    buildingIndicatorStyle.textContent = `
        .building-indicator {
            position: fixed;
            top: 10px;
            right: 100px;
            background-color: #f9f9f9;
            padding: 5px 10px;
            border-radius: 4px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            font-size: 14px;
            color: #333;
            z-index: 900;
        }
        .building-indicator.building-Villa {
            background-color: #d3f0e0;
        }
        .building-indicator.building-Kolibri {
            background-color: #d3e0f0;
        }
        .toggle-building-button {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 5px 10px;
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            z-index: 900;
        }
    `;
    document.head.appendChild(buildingIndicatorStyle);
    
    // Добавляем индикатор активного здания
    var buildingIndicator = document.createElement('div');
    buildingIndicator.className = 'building-indicator building-Villa';
    buildingIndicator.innerHTML = 'Активное здание: <strong>Villa</strong>';
    document.body.appendChild(buildingIndicator);
    
    // Добавляем кнопку переключения зданий
    var switchBuildingButton = document.createElement('button');
    switchBuildingButton.innerHTML = '🏢 Сменить здание';
    switchBuildingButton.className = 'toggle-building-button';
    document.body.appendChild(switchBuildingButton);
    
    // Обработчик переключения зданий
    switchBuildingButton.addEventListener('click', function() {
        activeBuilding = activeBuilding === 'Villa' ? 'Kolibri' : 'Villa';
        buildingIndicator.innerHTML = `Активное здание: <strong>${activeBuilding}</strong>`;
        buildingIndicator.className = `building-indicator building-${activeBuilding}`;
    });
    
    // Обработчик переключения режима
    addBlockButton.addEventListener('click', function() {
        addBlockMode = !addBlockMode;
        this.classList.toggle('active');
        
        // Включаем или выключаем подсветку ячеек в обоих зданиях
        document.querySelectorAll('.schedule-container').forEach(function(container) {
            var dataCells = container.querySelectorAll('.schedule-grid td:not(.time-cell)');
            dataCells.forEach(function(cell) {
                if (addBlockMode) {
                    cell.classList.add('cell-highlight');
                } else {
                    cell.classList.remove('cell-highlight');
                }
            });
        });
        
        // Показываем или скрываем индикатор активного здания и кнопку переключения
        buildingIndicator.style.display = addBlockMode ? 'block' : 'none';
        switchBuildingButton.style.display = addBlockMode ? 'block' : 'none';
    });
    
    // По умолчанию скрываем индикатор здания и кнопку переключения
    buildingIndicator.style.display = 'none';
    switchBuildingButton.style.display = 'none';
    
    // Обработчик кликов по ячейкам
    document.addEventListener('click', function(e) {
        if (!addBlockMode || window.editDialogOpen) return;
        
        var cell = e.target.closest('td:not(.time-cell)');
        if (!cell) return;
        
        // Определяем день и колонку
        var dayMatch = cell.className.match(/day-(\w+)/);
        if (!dayMatch) return;
        
        var day = dayMatch[1];
        var colIndex = parseInt(cell.getAttribute('data-col')) || 0;
        var rowIndex = parseInt(cell.getAttribute('data-row')) || 0;
        
        // Определяем здание, в котором находится ячейка
        var scheduleContainer = cell.closest('.schedule-container');
        var clickedBuilding = determineBuildingForContainer(scheduleContainer);
        
        // Если кликнуто по ячейке не в активном здании, меняем активное здание
        if (clickedBuilding !== activeBuilding) {
            activeBuilding = clickedBuilding;
            buildingIndicator.innerHTML = `Активное здание: <strong>${activeBuilding}</strong>`;
            buildingIndicator.className = `building-indicator building-${activeBuilding}`;
        }
        
        // Открываем диалог с предзаполненными значениями, используя активное здание
        openCreateBlockDialog(e, day, colIndex, rowIndex, activeBuilding);
    });
    
    // Вспомогательная функция для определения здания по контейнеру расписания
    function determineBuildingForContainer(container) {
        if (!container) return "Villa"; // По умолчанию, если не найден
        
        // Ищем заголовок здания перед контейнером
        var element = container.previousElementSibling;
        while (element) {
            if (element.tagName === 'H2') {
                if (element.textContent.includes('Villa')) return 'Villa';
                if (element.textContent.includes('Kolibri')) return 'Kolibri';
                break;
            }
            element = element.previousElementSibling;
        }
        
        return "Villa"; // По умолчанию, если не определено
    }
}

// Экспортируем функцию
window.initQuickAddByClick = initQuickAddByClick;