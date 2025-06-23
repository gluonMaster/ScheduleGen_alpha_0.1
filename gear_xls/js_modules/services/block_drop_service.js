// Сервис для обработки завершения перетаскивания блоков

var BlockDropService = (function() {
    'use strict';
    
    // Приватные методы
    function findClosestHeaderByPosition(block, day, table) {
        // Находим все заголовки для этого дня
        var dayHeaders = Array.from(table.querySelectorAll('th.day-' + day));
        
        // Фильтруем только видимые заголовки
        var visibleHeaders = dayHeaders.filter(function(header) {
            return window.getComputedStyle(header).display !== 'none';
        });
        
        if (visibleHeaders.length === 0) {
            return null;
        }
        
        // Найдем ближайший заголовок по горизонтали
        var closestHeader = null;
        var minDistance = Infinity;
        var bestColIndex = -1;
        
        var blockRect = block.getBoundingClientRect();
        var blockCenter = blockRect.left + blockRect.width / 2;
        
        for (var i = 0; i < visibleHeaders.length; i++) {
            var headerRect = visibleHeaders[i].getBoundingClientRect();
            var headerCenter = headerRect.left + headerRect.width / 2;
            
            var distance = Math.abs(blockCenter - headerCenter);
            if (distance < minDistance) {
                minDistance = distance;
                closestHeader = visibleHeaders[i];
                bestColIndex = i;
            }
        }
        
        return { header: closestHeader, colIndex: bestColIndex };
    }
    
    function updateBlockPositionData(block, day, colIndex, table) {
        var headerHeight = table.querySelector('thead').getBoundingClientRect().height;
        var currentTop = parseFloat(block.style.top);
        
        // ВОЗВРАЩАЕМ ПРОСТУЮ ЛОГИКУ СТАРОГО КОДА:
        // Определяем номер строки напрямую по текущей позиции блока
        var rowIndex = Math.round((currentTop - headerHeight) / (gridCellHeight + borderWidth));
        rowIndex = Math.max(0, rowIndex); // не может быть отрицательным
        
        // Вычисляем компенсацию для найденной строки (как в старом коде)
        var factor = window.compensationFactor || 0.4;
        var exponent = window.compensationExponent || 1.02;
        var compensation = Math.pow(rowIndex, exponent) * factor;
        
        // ПРАВИЛЬНО восстанавливаем исходную позицию (как в старом коде)
        var originalTopForNewPosition = currentTop + compensation;
        
        // Обновляем атрибуты блока
        block.setAttribute('data-col-index', colIndex);
        block.setAttribute('data-day', day);
        block.setAttribute('data-original-top', originalTopForNewPosition);
        block.setAttribute('data-compensated', 'false');
        
        // Обновляем класс для соответствия дню
        block.className = block.className.replace(/activity-day-\w+/, 'activity-day-' + day);
    }
    
    function calculateDayOffsets(table) {
        var dayOffsets = [];
        var cumWidth = 0;
        
        daysOrder.forEach(function(d) {
            var dayWidth = 0;
            var headers = table.querySelectorAll('th.day-' + d);
            headers.forEach(function(h) {
                if (window.getComputedStyle(h).display !== 'none') {
                    dayWidth += h.getBoundingClientRect().width;
                }
            });
            var startPx = cumWidth;
            var endPx = cumWidth + dayWidth;
            dayOffsets.push({ day: d, startPx: startPx, endPx: endPx });
            cumWidth = endPx;
        });
        
        return dayOffsets;
    }
    
    function determineDayFromPosition(block, container, table) {
        var containerStyle = window.getComputedStyle(container);
        var containerLeftPadding = parseFloat(containerStyle.paddingLeft) || 0;
        var absoluteLeft = parseFloat(block.style.left) || 0;
        
        // Смещение внутри контейнера (без учёта колонки времени и отступов)
        var offsetWithinContainer = absoluteLeft - containerLeftPadding - measuredTimeColWidth;
        if (offsetWithinContainer < 0) offsetWithinContainer = 0;
        
        var dayOffsets = calculateDayOffsets(table);
        
        // Определяем день
        var chosenDay = dayOffsets.find(function(obj) {
            return offsetWithinContainer >= obj.startPx && offsetWithinContainer < obj.endPx;
        });
        
        if (!chosenDay && dayOffsets.length > 0) {
            chosenDay = dayOffsets[dayOffsets.length - 1];
        } else if (!chosenDay) {
            chosenDay = { day: daysOrder[0], startPx: 0, endPx: dayCellWidth };
        }
        
        return chosenDay;
    }
    
    function calculateColumnIndexFromPosition(offsetWithinContainer, chosenDay, table) {
        var offsetWithinDay = offsetWithinContainer - chosenDay.startPx;
        var newColIndex = Math.floor(offsetWithinDay / dayCellWidth);
        
        // Получаем только ВИДИМЫЕ заголовки колонок выбранного дня
        var visibleHeaders = Array.from(table.querySelectorAll('th.day-' + chosenDay.day))
            .filter(function(header) {
                return window.getComputedStyle(header).display !== 'none';
            });
        
        // Проверяем границы индекса
        if (newColIndex < 0) {
            newColIndex = 0;
        }
        if (visibleHeaders.length > 0 && newColIndex >= visibleHeaders.length) {
            newColIndex = visibleHeaders.length - 1;
        }
        
        return newColIndex;
    }
      function fallbackProcessBlockDrop(block) {
        var container = block.parentElement;
        var table = container.querySelector('.schedule-grid');
        
        // Определяем день и колонку на основе позиции
        var chosenDay = determineDayFromPosition(block, container, table);
        
        var containerStyle = window.getComputedStyle(container);
        var containerLeftPadding = parseFloat(containerStyle.paddingLeft) || 0;
        var absoluteLeft = parseFloat(block.style.left) || 0;
        var offsetWithinContainer = absoluteLeft - containerLeftPadding - measuredTimeColWidth;
        if (offsetWithinContainer < 0) offsetWithinContainer = 0;
        
        var newColIndex = calculateColumnIndexFromPosition(offsetWithinContainer, chosenDay, table);
        
        // ИСПРАВЛЕНИЕ: Используем исправленную функцию обновления данных блока
        updateBlockPositionData(block, chosenDay.day, newColIndex, table);
        
        // Обновляем позиции всех блоков
        if (typeof updateActivityPositions === 'function') {
            updateActivityPositions();
        }
    }
    
    // Публичный API
    return {
        processBlockDrop: function(block) {
            var container = block.parentElement;
            var table = container.querySelector('.schedule-grid');
            var day = block.getAttribute('data-day');
            
            if (!day) {
                console.error('Атрибут data-day не найден в блоке');
                return;
            }
            
            // Пытаемся найти ближайший заголовок по позиции
            var headerResult = findClosestHeaderByPosition(block, day, table);
            
            if (headerResult && headerResult.header && headerResult.colIndex !== -1) {
                console.log('Найден ближайший заголовок:', headerResult.header, 'индекс:', headerResult.colIndex);
                
                // Обновляем данные блока
                updateBlockPositionData(block, day, headerResult.colIndex, table);
                
                // Обновляем позиции всех блоков
                if (typeof updateActivityPositions === 'function') {
                    updateActivityPositions();
                }
            } else {
                console.warn('Не удалось найти подходящий заголовок для блока, используем fallback');
                fallbackProcessBlockDrop(block);
            }
        }
    };
})();

// Делаем сервис глобально доступным
window.BlockDropService = BlockDropService;
