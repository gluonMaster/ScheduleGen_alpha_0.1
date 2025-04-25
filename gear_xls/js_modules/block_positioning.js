// Модуль для создания и позиционирования новых блоков занятий

// Функция для создания и добавления нового блока в расписание
function createNewBlock(building, day, colIndex, subject, teacher, students, room, timeRange, backgroundColor) {
    console.log(`Создание нового блока в здании: ${building}, день: ${day}, колонка: ${colIndex}`);
    
    // Находим контейнер расписания для указанного здания
    var container = findScheduleContainerForBuilding(building);
    if (!container) {
        console.error(`Не найден контейнер расписания для здания ${building}`);
        // Пробуем использовать первый контейнер как запасной вариант
        container = document.querySelector('.schedule-container');
        if (!container) {
            alert(`Ошибка: не найден контейнер расписания для здания ${building}`);
            return;
        }
    }
    
    // Создаем новый блок
    var newBlock = document.createElement('div');
    newBlock.className = `activity-block activity-day-${day}`;
    newBlock.setAttribute('data-day', day);
    newBlock.setAttribute('data-col-index', colIndex);
    newBlock.setAttribute('data-building', building);
    newBlock.setAttribute('data-compensated', 'false');
    
    // Применяем выбранный цвет фона
    newBlock.style.backgroundColor = backgroundColor || '#FFFBD3'; // Желтый по умолчанию, если цвет не указан
    
    // Определяем и устанавливаем контрастный цвет текста
    if (typeof getContrastTextColor === 'function') {
        newBlock.style.color = getContrastTextColor(newBlock.style.backgroundColor);
    }
    
    // ВАЖНО: устанавливаем фиксированную ширину 100px, такую же как у оригинальных блоков
    newBlock.style.width = '100px';
    
    // Устанавливаем содержимое блока
    newBlock.innerHTML = `<strong>${subject}</strong><br>${teacher}<br>${students}<br>${room}<br>${timeRange}`;
    
    // Добавляем блок в контейнер
    container.appendChild(newBlock);
    
    // Устанавливаем начальные позиции блока
    positionNewBlock(newBlock, timeRange);
    
    // Добавляем обработчики событий для нового блока
    addEventListenersToBlock(newBlock);
}

// Функция для позиционирования нового блока
function positionNewBlock(block, timeRange) {
    var container = block.parentElement;
    var table = container.querySelector('.schedule-grid');
    
    // Разбираем время
    var times = timeRange.match(/^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/);
    if (!times) {
        console.error('Некорректный формат времени:', timeRange);
        return;
    }
    
    var startHour = parseInt(times[1]);
    var startMinute = parseInt(times[2]);
    var endHour = parseInt(times[3]);
    var endMinute = parseInt(times[4]);
    
    // Время в минутах от начала суток
    var startMinutes = startHour * 60 + startMinute;
    var endMinutes = endHour * 60 + endMinute;
    
    // Определяем начало сетки (обычно 9:00)
    var gridStart = 9 * 60; // 09:00 в минутах
    
    // Рассчитываем количество интервалов с начала сетки
    var timeInterval = window.timeInterval || 5; // 5-минутные интервалы по умолчанию
    var startQuants = (startMinutes - gridStart) / timeInterval;
    var endQuants = (endMinutes - gridStart) / timeInterval;
    
    // Получаем высоту заголовка и ячейки
    var headerHeight = table.querySelector('thead').getBoundingClientRect().height;
    var cellHeight = window.gridCellHeight || 15;
    var borderWidth = window.borderWidth || 0.5;
    
    // Рассчитываем позицию top без компенсации
    var originalTop = headerHeight + (startQuants * cellHeight) + (startQuants * borderWidth);
    
    // Рассчитываем высоту блока
    var quantCount = endQuants - startQuants;
    var internalBorders = Math.max(0, quantCount - 1);
    var height = (quantCount * cellHeight) + (internalBorders * borderWidth * 0.5);
    
    // Устанавливаем оригинальную позицию без компенсации и высоту
    block.setAttribute('data-original-top', originalTop);
    block.style.height = height + 'px';
    
    // ВАЖНО: Ширина блока уже установлена в функции createNewBlock
    // Здесь мы не трогаем параметр width, чтобы сохранить фиксированное значение 100px
    
    // Обновляем позиции всех блоков для применения компенсации
    updateActivityPositions();
}

// Экспортируем функции для использования в других модулях
window.createNewBlock = createNewBlock;
window.positionNewBlock = positionNewBlock;