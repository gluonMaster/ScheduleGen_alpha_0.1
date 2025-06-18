// Модуль с вспомогательными функциями для работы с колонками в разных зданиях

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
    
    // Если вообще не нашли подходящей колонки, используем первую
    if (bestColIndex === -1 && dayHeaders.length > 0) {
        console.log(`Не найдено совпадений, использую первую колонку`);
        bestColIndex = 0;
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

// Экспортируем функции
window.findMatchingColumnInBuilding = findMatchingColumnInBuilding;
window.updateBlockColumnForBuilding = updateBlockColumnForBuilding;