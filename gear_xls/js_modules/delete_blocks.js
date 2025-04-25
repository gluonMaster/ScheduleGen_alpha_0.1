// Модуль для удаления блоков занятий из расписания

// Функция инициализации режима удаления блоков
function initDeleteBlocks() {
    // Добавляем кнопку для включения режима удаления
    addDeleteBlockButton();
}

// Функция для добавления кнопки удаления блоков в интерфейс
function addDeleteBlockButton() {
    // Создаем кнопку для включения режима удаления
    var deleteButton = document.createElement('button');
    deleteButton.id = 'delete-block-button';
    deleteButton.innerHTML = '🗑️';
    deleteButton.className = 'delete-block-button';
    deleteButton.title = 'Режим удаления блоков';
    
    // Находим блок с липкими кнопками
    var stickyButtons = document.querySelector('.sticky-buttons');
    if (stickyButtons) {
        // Добавляем кнопку в блок sticky-buttons
        stickyButtons.appendChild(deleteButton);
    } else {
        console.warn('Не найден блок .sticky-buttons для добавления кнопки удаления');
        return;
    }
    
    // Добавляем стили для кнопки удаления и режима удаления
    var style = document.createElement('style');
    style.textContent = `
        .delete-block-button {
            padding: 8px 16px;
            background-color: #f44336;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            margin: 5px;
            transition: background-color 0.3s;
        }
        .delete-block-button:hover {
            background-color: #d32f2f;
        }
        .delete-block-button.active {
            background-color: #d32f2f;
            box-shadow: 0 0 8px rgba(255, 0, 0, 0.5);
        }
        .delete-mode .activity-block {
            cursor: pointer;
            opacity: 0.8;
            transition: all 0.3s ease;
        }
        .delete-mode .activity-block:hover {
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.7);
            opacity: 1;
        }
        .delete-mode-indicator {
            position: fixed;
            top: 50px;
            left: 50%;
            transform: translateX(-50%);
            background-color: rgba(255, 0, 0, 0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            font-weight: bold;
            z-index: 9999;
            display: none;
        }
    `;
    document.head.appendChild(style);
    
    // Создаем индикатор режима удаления
    var deleteIndicator = document.createElement('div');
    deleteIndicator.className = 'delete-mode-indicator';
    deleteIndicator.textContent = 'РЕЖИМ УДАЛЕНИЯ АКТИВЕН';
    document.body.appendChild(deleteIndicator);
    
    // Переменная для отслеживания состояния режима удаления
    var deleteMode = false;
    
    // Обработчик нажатия на кнопку удаления
    deleteButton.addEventListener('click', function() {
        deleteMode = !deleteMode;
        
        // Обновляем состояние кнопки
        deleteButton.classList.toggle('active', deleteMode);
        
        // Показываем или скрываем индикатор режима удаления
        deleteIndicator.style.display = deleteMode ? 'block' : 'none';
        
        // Добавляем или удаляем класс режима удаления у документа
        document.body.classList.toggle('delete-mode', deleteMode);
        
        // Отключаем другие режимы, если они активны
        if (deleteMode) {
            // Отключаем режим добавления, если он активен
            var addModeButton = document.getElementById('toggle-add-mode');
            if (addModeButton && addModeButton.classList.contains('active')) {
                addModeButton.click();
            }
            
            // Добавляем обработчик для всех блоков
            enableDeleteHandlers();
        } else {
            // Удаляем обработчик при выключении режима
            disableDeleteHandlers();
        }
    });
    
    // Функция для добавления обработчиков удаления к блокам
    function enableDeleteHandlers() {
        // Получаем все блоки занятий
        var blocks = document.querySelectorAll('.activity-block');
        
        blocks.forEach(function(block) {
            // Добавляем обработчик клика для удаления
            block.addEventListener('click', handleBlockDelete);
            
            // Добавляем атрибут title для подсказки
            block.setAttribute('data-original-title', block.getAttribute('title') || '');
            block.setAttribute('title', 'Нажмите, чтобы удалить блок');
        });
    }
    
    // Функция для удаления обработчиков
    function disableDeleteHandlers() {
        // Получаем все блоки занятий
        var blocks = document.querySelectorAll('.activity-block');
        
        blocks.forEach(function(block) {
            // Удаляем обработчик клика
            block.removeEventListener('click', handleBlockDelete);
            
            // Восстанавливаем оригинальный title
            var originalTitle = block.getAttribute('data-original-title');
            if (originalTitle) {
                block.setAttribute('title', originalTitle);
            } else {
                block.removeAttribute('title');
            }
        });
    }
    
    // Обработчик удаления блока
    function handleBlockDelete(e) {
        if (!deleteMode) return;
        
        // Предотвращаем всплытие события
        e.preventDefault();
        e.stopPropagation();
        
        // Получаем блок, на который кликнули
        var block = e.currentTarget;
        
        // Получаем информацию о блоке для уведомления
        var building = block.getAttribute('data-building') || getBlockBuilding(block);
        var day = block.getAttribute('data-day');
        var subject = '';
        var teacher = '';
        var time = '';
        
        // Извлекаем информацию из содержимого блока
        var subjectElement = block.querySelector('strong');
        if (subjectElement) {
            subject = subjectElement.textContent || '';
        }
        
        var parts = block.innerHTML.split('<br>');
        if (parts.length > 1) teacher = parts[1].trim();
        if (parts.length > 4) time = parts[4].trim();
        
        // Запрашиваем подтверждение удаления
        var confirmMessage = `Вы действительно хотите удалить занятие?\n\nЗдание: ${building}\nДень: ${day}\nПредмет: ${subject}\nПреподаватель: ${teacher}\nВремя: ${time}`;
        
        if (confirm(confirmMessage)) {
            // Удаляем блок
            block.parentNode.removeChild(block);
            
            // Создаем уведомление об успешном удалении
            showNotification(`Занятие удалено: ${subject} (${time})`, 'success');
        }
    }
    
    // Функция для определения здания блока по его родительскому контейнеру
    function getBlockBuilding(block) {
        var container = block.closest('.schedule-container');
        if (!container) return "Неизвестно";
        
        var element = container.previousElementSibling;
        while (element) {
            if (element.tagName === 'H2') {
                if (element.textContent.includes('Villa')) return 'Villa';
                if (element.textContent.includes('Kolibri')) return 'Kolibri';
                break;
            }
            element = element.previousElementSibling;
        }
        
        return "Неизвестно";
    }
    
    // Функция для отображения уведомления
    function showNotification(message, type = 'info') {
        // Создаем элемент уведомления
        var notification = document.createElement('div');
        notification.className = 'notification ' + type;
        notification.textContent = message;
        
        // Добавляем стили для уведомления, если их еще нет
        if (!document.getElementById('notification-styles')) {
            var notificationStyles = document.createElement('style');
            notificationStyles.id = 'notification-styles';
            notificationStyles.textContent = `
                .notification {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    padding: 15px 25px;
                    border-radius: 4px;
                    font-weight: bold;
                    color: white;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    z-index: 9999;
                    animation: fadeIn 0.3s ease, fadeOut 0.3s ease 2.7s;
                    max-width: 350px;
                }
                .notification.info {
                    background-color: #2196F3;
                }
                .notification.success {
                    background-color: #4CAF50;
                }
                .notification.warning {
                    background-color: #FF9800;
                }
                .notification.error {
                    background-color: #F44336;
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes fadeOut {
                    from { opacity: 1; transform: translateY(0); }
                    to { opacity: 0; transform: translateY(-10px); }
                }
            `;
            document.head.appendChild(notificationStyles);
        }
        
        // Добавляем уведомление в DOM
        document.body.appendChild(notification);
        
        // Удаляем уведомление через 3 секунды
        setTimeout(function() {
            document.body.removeChild(notification);
        }, 3000);
    }
    
    // Клавиша Escape для выхода из режима удаления
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && deleteMode) {
            deleteButton.click(); // Выключаем режим удаления
        }
    });
}

// Экспортируем функцию инициализации
window.initDeleteBlocks = initDeleteBlocks;