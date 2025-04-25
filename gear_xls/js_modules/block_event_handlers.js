// Модуль с обработчиками событий для блоков занятий

// Функция для добавления обработчиков событий новому блоку
function addEventListenersToBlock(block) {
    // Отслеживаем состояние для определения двойного клика
    let clickTimeout = null;
    let isPotentialDoubleClick = false;
    
    block.addEventListener('mousedown', function(e) {
        // Если открыт диалог редактирования, не начинаем drag
        if (window.editDialogOpen || isPotentialDoubleClick) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }
        
        // Устанавливаем флаг потенциального двойного клика
        isPotentialDoubleClick = true;
        
        // Устанавливаем timeout для определения, был ли это одиночный клик
        clickTimeout = setTimeout(function() {
            // Если таймаут сработал до второго клика, значит это был одиночный клик
            isPotentialDoubleClick = false;
            
            if (!window.editDialogOpen) {
                window.draggedBlock = block;
                var rect = block.getBoundingClientRect();
                var offsetX = e.clientX - rect.left;
                var offsetY = e.clientY - rect.top;
                block.style.opacity = 0.7;
            }
        }, 200);
        
        e.preventDefault();
    });
    
    // Обработчик двойного клика
    block.addEventListener('dblclick', function(e) {
        // Очищаем таймаут и сбрасываем флаг
        if (clickTimeout) {
            clearTimeout(clickTimeout);
        }
        isPotentialDoubleClick = false;
        
        // Если был начат процесс перетаскивания, отменяем его
        if (window.draggedBlock === block) {
            window.draggedBlock.style.opacity = 1;
            window.draggedBlock = null;
        }
        
        // Предотвращаем запуск перетаскивания
        e.stopPropagation();
        e.preventDefault();
        
        // Сохраняем позицию блока перед редактированием
        var origLeft = block.style.left;
        var origTop = block.style.top;
        
        // Открываем диалог редактирования (передаем информацию о здании)
        if (!window.editDialogOpen) {
            var building = block.getAttribute('data-building') || 
                          determineBuildingForBlock(block);
            openEditDialog(block, origLeft, origTop, building);
        }
        
        // Функция для определения здания блока
        function determineBuildingForBlock(block) {
            var container = block.closest('.schedule-container');
            if (!container) return "Villa";
            
            var element = container.previousElementSibling;
            while (element) {
                if (element.tagName === 'H2') {
                    if (element.textContent.includes('Villa')) return 'Villa';
                    if (element.textContent.includes('Kolibri')) return 'Kolibri';
                    break;
                }
                element = element.previousElementSibling;
            }
            
            return "Villa";
        }
    });
}

// Экспортируем функцию для использования в других модулях
window.addEventListenersToBlock = addEventListenersToBlock;