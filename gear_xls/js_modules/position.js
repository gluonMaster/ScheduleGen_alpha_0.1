// Модуль для позиционирования элементов расписания

// Модифицированная функция обновления позиций activity-block
function updateActivityPositions() {
    document.querySelectorAll('.schedule-container').forEach(function(container) {
        var containerStyle = window.getComputedStyle(container);
        var containerLeftPadding = parseFloat(containerStyle.paddingLeft) || 0;

        var table = container.querySelector('.schedule-grid');
        var timeCell = table.querySelector('th.time-cell');
        var timeCellWidthMeasured = timeCell
            ? timeCell.getBoundingClientRect().width
            : 0; // fallback

        // Запоминаем измеренную ширину колонки времени
        measuredTimeColWidth = timeCellWidthMeasured;

        // Позиционируем каждый блок
        container.querySelectorAll('.activity-block').forEach(function(block) {
            var day = block.getAttribute('data-day');
            var colIndex = parseInt(block.getAttribute('data-col-index'));

            // Стартуем с реальной ширины колонки времени
            var leftOffset = timeCellWidthMeasured;

            // Прибавляем ширину всех предыдущих дней
            for (var i = 0; i < daysOrder.length; i++) {
                var d = daysOrder[i];
                if (d === day) break;
                var headers = table.querySelectorAll('th.day-' + d);
                headers.forEach(function(h) {
                    if (window.getComputedStyle(h).display !== 'none') {
                        leftOffset += h.getBoundingClientRect().width;
                    }
                });
            }

            // Прибавляем ширину нужного количества столбцов текущего дня
            var currentDayHeaders = table.querySelectorAll('th.day-' + day);
            for (var j = 0; j < colIndex; j++) {
                if (currentDayHeaders[j] && window.getComputedStyle(currentDayHeaders[j]).display !== 'none') {
                    leftOffset += currentDayHeaders[j].getBoundingClientRect().width;
                }
            }

            // Учитываем padding контейнера
            leftOffset = leftOffset + containerLeftPadding;
            block.style.left = leftOffset + 'px';

            // НАЧАЛО ЛОГИКИ КОМПЕНСАЦИИ
            
            // Получаем исходную позицию (если есть) или текущую позицию
            var originalTop;
            if (block.hasAttribute('data-original-top')) {
                originalTop = parseFloat(block.getAttribute('data-original-top'));
            } else {
                // Если нет атрибута, используем текущую позицию как исходную
                originalTop = parseFloat(block.style.top);
                block.setAttribute('data-original-top', originalTop);
            }
            
            var headerHeight = parseFloat(table.querySelector('thead').getBoundingClientRect().height);
            
            // Определяем номер строки от начала таблицы используя исходную позицию
            var rowIndex = Math.floor((originalTop - headerHeight) / (gridCellHeight + borderWidth));
            
            // Используем текущие настройки компенсации
            var factor = window.compensationFactor !== undefined ? window.compensationFactor : 0.4;
            var exponent = window.compensationExponent !== undefined ? window.compensationExponent : 1.02;
            
            // Рассчитываем компенсацию
            var compensation = Math.pow(rowIndex, exponent) * factor;
            
            // Применяем компенсацию к исходному положению
            block.style.top = (originalTop - compensation) + 'px';
            
            // Помечаем блок как имеющий компенсацию
            block.setAttribute('data-compensated', 'true');
            
            // КОНЕЦ ЛОГИКИ КОМПЕНСАЦИИ
        });
    });
}

// Делаем функцию глобально доступной
window.updateActivityPositions = updateActivityPositions;

// Функция для обновления позиции и размера блока при изменении времени
function updateBlockPosition(block, newTimeRange) {
    // Разбираем новое время
    var times = newTimeRange.match(/^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/);
    if (!times) {
        console.error('Некорректный формат времени:', newTimeRange);
        return;
    }
    
    var startHour = parseInt(times[1]);
    var startMinute = parseInt(times[2]);
    var endHour = parseInt(times[3]);
    var endMinute = parseInt(times[4]);
    
    // Время в минутах от начала суток
    var startMinutes = startHour * 60 + startMinute;
    var endMinutes = endHour * 60 + endMinute;
    
    // Определяем начало сетки (по умолчанию 9:00)
    var gridStart = 9 * 60; // 09:00 в минутах
    
    // Рассчитываем количество интервалов с начала сетки
    var timeInterval = 5; // 5-минутные интервалы
    var startQuants = (startMinutes - gridStart) / timeInterval;
    var endQuants = (endMinutes - gridStart) / timeInterval;
    
    // Получаем текущую высоту заголовка и ячейки
    var container = block.parentElement;
    var table = container.querySelector('.schedule-grid');
    var headerHeight = table.querySelector('thead').getBoundingClientRect().height;
    var cellHeight = window.gridCellHeight || 15;
    var borderWidth = window.borderWidth || 0.5;
    
    // Рассчитываем новую позицию без компенсации
    var newOriginalTop = headerHeight + (startQuants * cellHeight) + (startQuants * borderWidth);
    
    var quantCount = endQuants - startQuants;
    var internalBorders = Math.max(0, quantCount - 1);
    var height = (quantCount * cellHeight) + (internalBorders * borderWidth * 0.5);
    
    // Отладочная информация
    console.log('Обновление позиции блока:', {
        newTime: newTimeRange,
        startMinutes: startMinutes,
        endMinutes: endMinutes,
        startQuants: startQuants,
        endQuants: endQuants,
        newOriginalTop: newOriginalTop,
        height: height
    });
    
    // Сохраняем исходную позицию без компенсации
    block.setAttribute('data-original-top', newOriginalTop);
    
    // Устанавливаем высоту блока
    block.style.height = height + 'px';
    
    // Сбрасываем флаг компенсации, чтобы новая компенсация была применена при updateActivityPositions
    block.setAttribute('data-compensated', 'false');
}

// Функция для обновления колонки блока при изменении кабинета
function updateBlockColumn(block, newRoom) {
    var container = block.parentElement;
    var table = container.querySelector('.schedule-grid');
    var day = block.getAttribute('data-day');
    
    if (!day) {
        console.error('Не найден атрибут data-day у блока');
        return;
    }
    
    // Получаем все заголовки колонок текущего дня
    var dayHeaders = table.querySelectorAll('th.day-' + day);
    var newColIndex = -1;
    
    console.log('Поиск кабинета:', newRoom, 'в заголовках дня:', day);
    console.log('Количество найденных заголовков:', dayHeaders.length);
    
    // Ищем заголовок с указанным кабинетом
    for (var i = 0; i < dayHeaders.length; i++) {
        var headerText = dayHeaders[i].innerText || dayHeaders[i].textContent;
        console.log('Заголовок ' + i + ':', headerText);
        
        if (headerText.includes(newRoom)) {
            newColIndex = i;
            console.log('Найдено соответствие в колонке:', i);
            break;
        }
    }
    
    // Если не нашли точное соответствие, проверяем частичное соответствие
    if (newColIndex === -1) {
        for (var i = 0; i < dayHeaders.length; i++) {
            var headerText = dayHeaders[i].innerText || dayHeaders[i].textContent;
            // Удаляем название дня из заголовка и проверяем, что осталось
            var roomPart = headerText.replace(day, '').trim();
            console.log('Часть кабинета в заголовке ' + i + ':', roomPart);
            
            if (roomPart === newRoom) {
                newColIndex = i;
                console.log('Найдено частичное соответствие в колонке:', i);
                break;
            }
        }
    }
    
    // Если нашли колонку для нового кабинета
    if (newColIndex !== -1) {
        var currentColIndex = parseInt(block.getAttribute('data-col-index'));
        if (newColIndex !== currentColIndex) {
            console.log('Обновление колонки с', currentColIndex, 'на', newColIndex);
            
            // Обновляем атрибут колонки
            block.setAttribute('data-col-index', newColIndex);
            
            // Вызываем обновление позиции блока
            updateActivityPositions();
        } else {
            console.log('Колонка не изменилась');
        }
    } else {
        console.warn('Не найдена колонка для кабинета:', newRoom);
    }
}
