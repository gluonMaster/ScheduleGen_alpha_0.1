// Модуль с обработчиками событий для блоков занятий
// ОБНОВЛЕН: использует BuildingService вместо дублированных функций

// Функция для добавления обработчиков событий новому блоку
function addEventListenersToBlock(block) {
    function canUseLegacyBlockEvents(targetBlock) {
        var authUi = window.SchedGenAuthUI || null;
        var role = window.USER_ROLE || 'viewer';
        var lessonType = targetBlock ? (targetBlock.getAttribute('data-lesson-type') || 'group') : 'group';

        if (!targetBlock) return false;
        if (lessonType === 'veranstaltung') return false;
        if (authUi && typeof authUi.isEditMode === 'function' && !authUi.isEditMode()) return false;
        if (authUi && typeof authUi.canMutateBlock === 'function') {
            return authUi.canMutateBlock(role, targetBlock);
        }
        if (role === 'admin') return true;
        if (role === 'editor') return lessonType !== 'group';
        if (role === 'organizer') return lessonType === 'trial';
        return false;
    }

    // Отслеживаем состояние для определения двойного клика
    let clickTimeout = null;
    let isPotentialDoubleClick = false;
    
    block.addEventListener('mousedown', function(e) {
        if (!canUseLegacyBlockEvents(block)) {
            return;
        }
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
        if (!canUseLegacyBlockEvents(block)) {
            return;
        }
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
            // ИСПОЛЬЗУЕМ BuildingService для определения здания блока
            var building = block.getAttribute('data-building') || 
                          BuildingService.determineBuildingForBlock(block);
            openEditDialog(block, origLeft, origTop, building);
        }
    });
}

// Экспортируем функцию для использования в других модулях
window.addEventListenersToBlock = addEventListenersToBlock;
