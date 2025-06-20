// Сервис для управления drag & drop функциональностью блоков расписания

var DragDropService = (function() {
    'use strict';
    
    // Приватные переменные
    var preventDrag = false;
    var offsetX = 0;
    var offsetY = 0;
    var draggedBlock = null;
    
    // Приватные методы
    function initializeBlockEvents() {
        document.querySelectorAll('.activity-block').forEach(function(block) {
            // Отслеживаем состояние для определения двойного клика
            let clickTimeout = null;
            let isPotentialDoubleClick = false;
            
            block.addEventListener('mousedown', function(e) {
                // Если открыт диалог редактирования или установлен флаг preventDrag, не начинаем drag
                if (window.editDialogOpen || preventDrag || isPotentialDoubleClick) {
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }
                
                // Устанавливаем флаг потенциального двойного клика
                isPotentialDoubleClick = true;
                
                // Устанавливаем timeout для определения, был ли это одиночный клик
                clickTimeout = setTimeout(function() {
                    // Если таймаут сработал до второго клика, значит это был одиночный клик
                    // и можно начать перетаскивание
                    isPotentialDoubleClick = false;
                    
                    if (!window.editDialogOpen && !preventDrag) {
                        startDrag(block, e);
                    }
                }, 200); // 200 мс - стандартное время для определения двойного клика
                
                e.preventDefault(); // Предотвращаем выделение текста при перетаскивании
            });
            
            // Обработчик двойного клика
            block.addEventListener('dblclick', function(e) {
                handleDoubleClick(block, e, clickTimeout, isPotentialDoubleClick);
                isPotentialDoubleClick = false;
                clickTimeout = null;
            });
        });
        
        // Глобальные обработчики для перемещения и отпускания
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    }
    
    function startDrag(block, event) {
        draggedBlock = block;
        window.draggedBlock = block; // Поддерживаем совместимость с существующим кодом
        
        var rect = block.getBoundingClientRect();
        offsetX = event.clientX - rect.left;
        offsetY = event.clientY - rect.top;
        block.style.opacity = 0.7;
    }
    
    function handleDoubleClick(block, event, clickTimeout, isPotentialDoubleClick) {
        // Очищаем таймаут
        if (clickTimeout) {
            clearTimeout(clickTimeout);
        }
        
        // Устанавливаем флаг предотвращения drag на короткое время
        preventDrag = true;
        setTimeout(() => { preventDrag = false; }, 500);
        
        // Если был начат процесс перетаскивания, отменяем его
        if (draggedBlock === block) {
            draggedBlock.style.opacity = 1;
            draggedBlock = null;
            window.draggedBlock = null;
        }
        
        // Предотвращаем запуск перетаскивания
        event.stopPropagation();
        event.preventDefault();
        
        // Сохраняем позицию блока перед редактированием
        var origLeft = block.style.left;
        var origTop = block.style.top;
        
        // Открываем диалог редактирования только если не открыт
        if (!window.editDialogOpen) {
            openEditDialog(block, origLeft, origTop);
        }
    }
    
    function handleMouseMove(event) {
        if (draggedBlock && !window.editDialogOpen && !preventDrag) {
            var container = draggedBlock.parentElement;
            var rect = container.getBoundingClientRect();
            var scrollX = container.scrollLeft;
            var scrollY = container.scrollTop;
            var newLeft = event.clientX - rect.left - offsetX + scrollX;
            var newTop = event.clientY - rect.top - offsetY + scrollY;
            
            // Используем GridSnapService для привязки к сетке
            if (typeof GridSnapService !== 'undefined') {
                var snapped = GridSnapService.snapToGrid(newLeft, newTop, draggedBlock);
                draggedBlock.style.left = snapped.left + 'px';
                draggedBlock.style.top = snapped.top + 'px';
            } else {
                // Fallback без привязки к сетке
                draggedBlock.style.left = newLeft + 'px';
                draggedBlock.style.top = newTop + 'px';
            }
        }
    }
    
    function handleMouseUp(event) {
        if (draggedBlock && !window.editDialogOpen) {
            draggedBlock.style.opacity = 1;
            
            // Используем BlockDropService для обработки завершения перетаскивания
            if (typeof BlockDropService !== 'undefined') {
                BlockDropService.processBlockDrop(draggedBlock);
            } else {
                // Fallback - используем старую функцию
                if (typeof processBlockDrop === 'function') {
                    processBlockDrop(draggedBlock);
                }
            }
            
            draggedBlock = null;
            window.draggedBlock = null;
        }
    }
    
    // Публичный API
    return {
        init: function() {
            initializeBlockEvents();
        },
        
        getDraggedBlock: function() {
            return draggedBlock;
        },
        
        isDragging: function() {
            return draggedBlock !== null;
        },
        
        setPreventDrag: function(value) {
            preventDrag = value;
        }
    };
})();

// Делаем сервис глобально доступным
window.DragDropService = DragDropService;
