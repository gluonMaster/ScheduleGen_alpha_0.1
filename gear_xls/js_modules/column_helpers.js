// Модуль с вспомогательными функциями для работы с колонками в разных зданиях

// Глобальная переменная с порядком дней недели (если ещё не определена)
if (typeof window.daysOrder === 'undefined') {
    window.daysOrder = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
}

// Функция для поиска подходящей колонки в заданном здании
function findMatchingColumnInBuilding(day, room, building) {
    // Находим контейнер расписания для указанного здания
    var container = BuildingService.findScheduleContainerForBuilding(building);
    if (!container) {
        console.error(`Не найден контейнер расписания для здания ${building}`);
        return -1;
    }
    
    // Получаем все заголовки колонок для указанного дня в этом здании
    var dayHeaders = container.querySelectorAll(`.schedule-grid th.day-${day}`);
    var bestColIndex = -1;
    
    console.log(`Поиск колонки для кабинета ${room} в здании ${building} в день ${day}`);
    console.log(`Найдено ${dayHeaders.length} заголовков`);
    
    // Ищем точное совпадение номера кабинета в заголовке
    for (var i = 0; i < dayHeaders.length; i++) {
        var headerText = dayHeaders[i].textContent.trim();
        console.log(`Заголовок ${i}: "${headerText}"`);
        
        if (headerText.includes(room)) {
            console.log(`Найдено точное совпадение в колонке ${i}`);
            bestColIndex = i;
            break;
        }
    }
    
    // Если точного совпадения не найдено, ищем частичное
    if (bestColIndex === -1) {
        for (var i = 0; i < dayHeaders.length; i++) {
            var headerText = dayHeaders[i].textContent.trim();
            // Удаляем название дня из заголовка
            var roomPart = headerText.replace(day, '').trim();
            
            if (roomPart === room) {
                console.log(`Найдено частичное совпадение в колонке ${i}`);
                bestColIndex = i;
                break;
            }
        }
    }
    
    // Возвращаем -1 если колонка не найдена (для последующего создания новой)
    if (bestColIndex === -1) {
        console.log(`Колонка для кабинета ${room} не найдена в дне ${day} здания ${building}`);
    }
    
    return bestColIndex;
}

// Функция для обновления колонки блока при перемещении в другое здание
function updateBlockColumnForBuilding(block, room, building, day) {
    day = day || block.getAttribute('data-day');
    
    // Находим подходящую колонку в новом здании
    var colIndex = findMatchingColumnInBuilding(day, room, building);
    if (colIndex === -1) {
        console.warn(`Не удалось найти подходящую колонку для кабинета ${room} в здании ${building}`);
        colIndex = 0; // Используем первую колонку, если не нашли подходящей
    }
    
    // Обновляем атрибуты блока
    block.setAttribute('data-col-index', colIndex);
    
    return colIndex;
}

// Helper функция для форматирования заголовка день-кабинет
function formatDayRoomHeader(day, room, building) {
    // Находим контейнер расписания для указанного здания
    var container = BuildingService.findScheduleContainerForBuilding(building);
    if (!container) {
        console.warn(`Не найден контейнер расписания для здания ${building}, используем формат без пробела`);
        return day + room;
    }
    
    // Ищем первый существующий заголовок для этого дня
    var firstDayHeader = container.querySelector(`.schedule-grid th.day-${day}`);
    if (!firstDayHeader) {
        console.warn(`Не найдены заголовки для дня ${day} в здании ${building}, используем формат без пробела`);
        return day + room;
    }
    
    var headerText = firstDayHeader.textContent.trim();
    console.log(`Анализ формата заголовка: "${headerText}"`);
    
    // Определяем, есть ли пробел между днем и кабинетом
    // Заголовок содержит <br>, поэтому анализируем часть после <br>
    var headerParts = firstDayHeader.innerHTML.split('<br>');
    if (headerParts.length >= 2) {
        var roomPart = headerParts[1].trim();
        var dayPart = headerParts[0].trim();
        
        // Если в исходном тексте есть пробел после дня, добавляем его
        if (headerText.includes(dayPart + ' ')) {
            console.log(`Обнаружен формат с пробелом: "${day} ${room}"`);
            return day + ' ' + room;
        }
    }
    
    console.log(`Обнаружен формат без пробела: "${day}${room}"`);
    return day + room;
}

// Функция для создания новой колонки, если она отсутствует
function addColumnIfMissing(day, room, building) {
    console.log(`Попытка добавления колонки: день=${day}, кабинет=${room}, здание=${building}`);
    
    // Находим контейнер расписания для указанного здания
    var container = BuildingService.findScheduleContainerForBuilding(building);
    if (!container) {
        console.error(`Не найден контейнер расписания для здания ${building}`);
        return -1;
    }
    
    var table = container.querySelector('.schedule-grid');
    if (!table) {
        console.error(`Не найдена таблица расписания в здании ${building}`);
        return -1;
    }
    
    // Собираем заголовки для указанного дня
    var dayHeaders = Array.from(table.querySelectorAll(`thead th.day-${day}`));
    console.log(`Найдено ${dayHeaders.length} заголовков для дня ${day}`);
    
    // Проверяем, существует ли уже колонка с этим кабинетом
    for (var i = 0; i < dayHeaders.length; i++) {
        var headerText = dayHeaders[i].textContent.trim();
        console.log(`Проверка существующего заголовка ${i}: "${headerText}"`);
        if (headerText.includes(room)) {
            console.log(`Колонка для кабинета ${room} уже существует в позиции ${i}`);
            return i;
        }
    }
    
    // Кабинет не найден, нужно создать новую колонку
    console.log(`Создание новой колонки для кабинета ${room}`);
    
    // Определяем позицию для вставки (в конце группы дня)
    var insertionIndex = dayHeaders.length;
    
    // Форматируем заголовок новой колонки
    var newHeaderText = formatDayRoomHeader(day, room, building);
    
    // Создаем новый заголовок
    var newHeader = document.createElement('th');
    newHeader.className = 'day-' + day;
    newHeader.innerHTML = day + '<br>' + room;
    
    // Находим позицию для вставки в thead
    var thead = table.querySelector('thead tr');
    var insertPosition = findInsertPositionInHeader(thead, day, insertionIndex);
    
    console.log(`Позиция для вставки в thead: ${insertPosition} (из ${thead.children.length} колонок)`);
    
    if (insertPosition < thead.children.length) {
        thead.insertBefore(newHeader, thead.children[insertPosition]);
        console.log(`Заголовок вставлен ПЕРЕД элементом в позиции ${insertPosition}`);
    } else {
        thead.appendChild(newHeader);
        console.log(`Заголовок добавлен В КОНЕЦ thead`);
    }
    
    // Добавляем соответствующие ячейки в каждую строку tbody
    var tbody = table.querySelector('tbody');
    var rows = tbody.querySelectorAll('tr');
    
    console.log(`Добавление ячеек в ${rows.length} строк tbody в позицию ${insertPosition}`);
    
    for (var r = 0; r < rows.length; r++) {
        var newCell = document.createElement('td');
        newCell.className = 'day-' + day;
        newCell.setAttribute('data-row', r);
        newCell.setAttribute('data-col', insertionIndex);
        
        if (insertPosition < rows[r].children.length) {
            rows[r].insertBefore(newCell, rows[r].children[insertPosition]);
        } else {
            rows[r].appendChild(newCell);
        }
    }
    
    console.log(`Ячейки tbody добавлены успешно`);
    
    // Обновляем data-col-index для существующих блоков того же дня и здания
    console.log(`Обновление data-col-index для существующих блоков дня ${day} в здании ${building}`);
    updateExistingBlocksColIndex(building, day, insertionIndex);
    
    // НЕ вызываем updateActivityPositions здесь - это будет сделано в вызывающем коде
    // if (typeof updateActivityPositions === 'function') {
    //     updateActivityPositions();
    // }
    
    console.log(`Новая колонка создана для кабинета ${room} в позиции ${insertionIndex}`);
    return insertionIndex;
}

// Вспомогательная функция для определения позиции вставки в заголовке
function findInsertPositionInHeader(headerRow, day, insertionIndex) {
    var position = 1; // Начинаем после колонки времени
    
    // Используем глобальную переменную daysOrder
    var daysOrder = window.daysOrder || ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
    
    // Проходим все дни в порядке daysOrder до нашего дня
    for (var d = 0; d < daysOrder.length; d++) {
        if (daysOrder[d] === day) {
            // Добавляем количество существующих колонок для этого дня
            var existingCols = headerRow.querySelectorAll('.day-' + day).length;
            position += existingCols;
            break;
        } else {
            // Добавляем количество колонок для предыдущих дней
            var dayColCount = headerRow.querySelectorAll('.day-' + daysOrder[d]).length;
            position += dayColCount;
        }
    }
    
    return position;
}

// Функция для обновления data-col-index у существующих блоков
function updateExistingBlocksColIndex(building, day, insertionIndex) {
    var container = BuildingService.findScheduleContainerForBuilding(building);
    if (!container) return;
    
    var blocks = container.querySelectorAll(`.activity-block[data-day="${day}"][data-building="${building}"]`);
    
    for (var i = 0; i < blocks.length; i++) {
        var block = blocks[i];
        var currentColIndex = parseInt(block.getAttribute('data-col-index'));
        
        // Если колонка блока >= позиции вставки, увеличиваем на 1
        if (currentColIndex >= insertionIndex) {
            var newColIndex = currentColIndex + 1;
            block.setAttribute('data-col-index', newColIndex);
            console.log(`Обновлен data-col-index блока с ${currentColIndex} на ${newColIndex}`);
        }
    }
}

// Экспортируем функции
window.findMatchingColumnInBuilding = findMatchingColumnInBuilding;
window.updateBlockColumnForBuilding = updateBlockColumnForBuilding;
window.addColumnIfMissing = addColumnIfMissing;
window.formatDayRoomHeader = formatDayRoomHeader;