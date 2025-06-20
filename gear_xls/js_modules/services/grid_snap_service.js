// Сервис для привязки блоков к сетке расписания

var GridSnapService = (function() {
    'use strict';
    
    // Приватные методы
    function findClosestCell(absoluteLeft, absoluteTop, container) {
        var table = container.querySelector('.schedule-grid');
        var containerRect = container.getBoundingClientRect();
        
        // Находим все ячейки расписания (кроме ячеек времени)
        var dayCells = Array.from(table.querySelectorAll('td:not(.time-cell)'));
        
        if (dayCells.length === 0) {
            return null;
        }
        
        // Группируем ячейки по дням
        var cellsByDay = {};
        dayCells.forEach(function(cell) {
            var day = cell.className.match(/day-(\w+)/);
            if (day && day[1]) {
                if (!cellsByDay[day[1]]) {
                    cellsByDay[day[1]] = [];
                }
                cellsByDay[day[1]].push(cell);
            }
        });
        
        // Находим ближайшую ячейку
        var closestCell = null;
        var minDistance = Infinity;
        
        for (var day in cellsByDay) {
            cellsByDay[day].forEach(function(cell) {
                // Проверяем только видимые ячейки
                if (window.getComputedStyle(cell).display !== 'none') {
                    var cellRect = cell.getBoundingClientRect();
                    var cellCenterX = cellRect.left + cellRect.width / 2;
                    var cellCenterY = cellRect.top + cellRect.height / 2;
                    
                    // Используем взвешенное расстояние, чтобы горизонтальное расстояние 
                    // было более значимым для привязки
                    var distanceX = Math.abs(absoluteLeft - cellCenterX);
                    var distanceY = Math.abs(absoluteTop - cellCenterY);
                    var distance = distanceX * 2 + distanceY;
                    
                    if (distance < minDistance) {
                        minDistance = distance;
                        closestCell = cell;
                    }
                }
            });
        }
        
        return closestCell;
    }
    
    function snapToClosestCell(closestCell, container, block) {
        var table = container.querySelector('.schedule-grid');
        var containerRect = container.getBoundingClientRect();
        var containerStyle = window.getComputedStyle(container);
        var padTop = parseFloat(containerStyle.paddingTop) || 0;
        
        var closestCellRect = closestCell.getBoundingClientRect();
        var day = closestCell.className.match(/day-(\w+)/)[1];
        var colIndex = parseInt(closestCell.getAttribute('data-col')) || 0;
        var rowIndex = parseInt(closestCell.getAttribute('data-row')) || 0;
        
        // Определяем точные координаты для привязки
        var dayHeaders = table.querySelectorAll('th.day-' + day);
        var headerLeftPosition = 0;
        var headerHeight = table.querySelector('thead').getBoundingClientRect().height;
        
        if (dayHeaders.length > 0) {
            // Если у нас есть заголовки дня, используем их для определения левой позиции
            var dayHeaderRect = dayHeaders[colIndex].getBoundingClientRect();
            headerLeftPosition = dayHeaderRect.left - containerRect.left + container.scrollLeft;
        } else {
            // Запасной вариант - используем позицию ячейки
            headerLeftPosition = closestCellRect.left - containerRect.left + container.scrollLeft;
        }
        
        // Устанавливаем точное позиционирование
        var snappedLeft = headerLeftPosition;
        var snappedTop = headerHeight + padTop + (rowIndex * (gridCellHeight + borderWidth));
        
        // Обновляем data-аттрибуты блока
        block.setAttribute('data-day', day);
        block.setAttribute('data-col-index', colIndex);
        block.setAttribute('data-compensated', 'false');
        
        // Сохраняем исходное положение блока без компенсации
        block.setAttribute('data-original-top', snappedTop);
        
        // Обновляем класс для соответствия новому дню
        block.className = block.className.replace(/activity-day-\w+/, 'activity-day-' + day);
        
        return { left: snappedLeft, top: snappedTop };
    }
    
    function snapToGridFallback(left, top, block) {
        var container = block.parentElement;
        var containerRect = container.getBoundingClientRect();
        var containerStyle = window.getComputedStyle(container);
        var padLeft = parseFloat(containerStyle.paddingLeft) || 0;
        var padTop = parseFloat(containerStyle.paddingTop) || 0;
        
        var table = container.querySelector('.schedule-grid');
        var timeCell = table.querySelector('th.time-cell');
        var timeCellWidth = timeCell ? timeCell.getBoundingClientRect().width : measuredTimeColWidth;
        var headerHeight = table.querySelector('thead').getBoundingClientRect().height;
        
        // Получаем смещение внутри контейнера для определения дня
        var offsetWithinContainer = left - timeCellWidth - padLeft;
        if (offsetWithinContainer < 0) offsetWithinContainer = 0;
        
        // Собираем интервалы ширины по дням
        var dayOffsets = calculateDayOffsets(table);
        
        // Определяем день по смещению
        var chosenDay = findDayByOffset(offsetWithinContainer, dayOffsets);
        
        // Вычисляем индекс столбца в рамках выбранного дня
        var newColIndex = calculateColumnIndex(offsetWithinContainer, chosenDay, table);
        
        // Рассчитываем позиции
        var snappedLeft = calculateLeftPosition(timeCellWidth, padLeft, chosenDay, newColIndex, table);
        var rowIndex = Math.round((top - headerHeight - padTop) / (gridCellHeight + borderWidth));
        var snappedTop = headerHeight + padTop + (rowIndex * (gridCellHeight + borderWidth));
        
        // Обновляем атрибуты блока
        updateBlockAttributes(block, chosenDay.day, newColIndex, snappedTop);
        
        return { left: snappedLeft, top: snappedTop };
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
    
    function findDayByOffset(offsetWithinContainer, dayOffsets) {
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
    
    function calculateColumnIndex(offsetWithinContainer, chosenDay, table) {
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
    
    function calculateLeftPosition(timeCellWidth, padLeft, chosenDay, newColIndex, table) {
        var leftOffset = timeCellWidth + padLeft;
        
        // Прибавляем ширину всех предыдущих дней
        for (var i = 0; i < daysOrder.length; i++) {
            var d = daysOrder[i];
            if (d === chosenDay.day) break;
            var headers = table.querySelectorAll('th.day-' + d);
            headers.forEach(function(h) {
                if (window.getComputedStyle(h).display !== 'none') {
                    leftOffset += h.getBoundingClientRect().width;
                }
            });
        }
        
        // Прибавляем ширину нужного количества колонок текущего дня
        var visibleHeaders = Array.from(table.querySelectorAll('th.day-' + chosenDay.day))
            .filter(function(header) {
                return window.getComputedStyle(header).display !== 'none';
            });
        
        for (var j = 0; j < newColIndex; j++) {
            if (visibleHeaders[j]) {
                leftOffset += visibleHeaders[j].getBoundingClientRect().width;
            }
        }
        
        return leftOffset;
    }
    
    function updateBlockAttributes(block, day, colIndex, snappedTop) {
        block.setAttribute('data-day', day);
        block.setAttribute('data-col-index', colIndex);
        block.setAttribute('data-compensated', 'false');
        block.setAttribute('data-original-top', snappedTop);
        
        // Обновляем класс дня
        block.className = block.className.replace(/activity-day-\w+/, 'activity-day-' + day);
    }
    
    // Публичный API
    return {
        snapToGrid: function(left, top, block) {
            var container = block.parentElement;
            var containerRect = container.getBoundingClientRect();
            var containerStyle = window.getComputedStyle(container);
            var padLeft = parseFloat(containerStyle.paddingLeft) || 0;
            var padTop = parseFloat(containerStyle.paddingTop) || 0;
            
            // Рассчитываем абсолютную позицию (относительно окна)
            var absoluteLeft = left + containerRect.left - container.scrollLeft;
            var absoluteTop = top + containerRect.top - container.scrollTop;
            
            // Сначала пытаемся найти ближайшую ячейку
            var closestCell = findClosestCell(absoluteLeft, absoluteTop, container);
            
            if (closestCell) {
                return snapToClosestCell(closestCell, container, block);
            } else {
                // Fallback к традиционному методу
                return snapToGridFallback(left, top, block);
            }
        }
    };
})();

// Делаем сервис глобально доступным
window.GridSnapService = GridSnapService;
