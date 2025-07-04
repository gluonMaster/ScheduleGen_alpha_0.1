// Модуль для экспорта расписания в Excel

// Функция для сбора данных со всех блоков занятий
function collectScheduleData() {
    // Структура для хранения данных расписания
    var scheduleData = [];

    // Проходим по всем контейнерам расписания (по зданиям)
    document.querySelectorAll('.schedule-container').forEach(function(container) {
        var building = container.getAttribute('data-building');
        
        // Получаем таблицу и высоту заголовка
        var table = container.querySelector('.schedule-grid');
        var headerHeight = table.querySelector('thead').getBoundingClientRect().height;
        
        // Получаем начало сетки расписания в минутах (по умолчанию 9:00)
        var gridStart = 9 * 60; // 09:00 в минутах
        
        // Проходим по всем блокам активностей в этом здании
        container.querySelectorAll('.activity-block').forEach(function(block) {
            // Пропускаем скрытые блоки
            if (window.getComputedStyle(block).display === 'none') {
                return;
            }
            
            // Извлекаем данные из блока
            var day = block.getAttribute('data-day');
            var colIndex = parseInt(block.getAttribute('data-col-index'));
            
            // Получаем оригинальную позицию (без компенсации)
            var originalTop = parseFloat(block.getAttribute('data-original-top') || block.style.top);
            var blockHeight = parseFloat(block.style.height);
            
            // Получаем заголовок колонки для определения кабинета
            var roomName = '';
            var roomDisplay = '';
            var dayHeaders = table.querySelectorAll('th.day-' + day);
            if (dayHeaders.length > colIndex) {
                var headerContent = dayHeaders[colIndex].innerText.trim();
                // Удаляем из текста код дня (Mo, Di и т.д.)
                roomName = headerContent.replace(day, '').trim();
                // Сохраняем отображаемое имя кабинета
                roomDisplay = roomName;
            }
            
            // Извлекаем текстовое содержимое блока для получения остальных данных
            var blockContent = block.innerHTML;
            var lines = blockContent
                .replace(/<br>/g, '\n')  // Заменяем <br> на переносы строк
                .replace(/<[^>]*>/g, '') // Удаляем все HTML-теги
                .split('\n')              // Разбиваем по строкам
                .map(line => line.trim()) // Удаляем лишние пробелы
                .filter(line => line);    // Удаляем пустые строки
            
            // Извлекаем время начала и конца из содержимого блока
            var timeMatch = null;
            var startTime = '';
            var endTime = '';
            var duration = 0;
            
            // Ищем строку с временем в последних строках
            for (var i = lines.length - 1; i >= 0; i--) {
                timeMatch = lines[i].match(/(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})/);
                if (timeMatch) {
                    startTime = timeMatch[1];
                    endTime = timeMatch[2];
                    
                    // Вычисляем продолжительность из извлеченного времени
                    var startParts = startTime.split(':');
                    var endParts = endTime.split(':');
                    var startMinutes = parseInt(startParts[0]) * 60 + parseInt(startParts[1]);
                    var endMinutes = parseInt(endParts[0]) * 60 + parseInt(endParts[1]);
                    
                    // Проверяем, что время логично
                    if (startMinutes < endMinutes && startMinutes >= 0 && endMinutes <= 24*60) {
                        duration = endMinutes - startMinutes;
                        break;
                    } else {
                        console.warn('Извлеченное время выглядит неверно: ' + startTime + '-' + endTime);
                        timeMatch = null; // Сбрасываем, чтобы использовать резервный метод
                    }
                }
            }
            
            // Если время не найдено в содержимом блока, используем расчет по позиции (резервный вариант)
            if (!timeMatch) {
                console.warn('Время не найдено в содержимом блока, используем расчет по позиции для блока: ' + 
                            (lines[0] || 'неизвестный') + ' в кабинете ' + (roomName || 'неизвестен') + 
                            ' в день ' + day + ' в здании ' + building);
                
                var rowIndex = Math.floor((originalTop - headerHeight) / (gridCellHeight + borderWidth));
                var startMinutes = gridStart + (rowIndex * timeInterval);
                
                var rowSpan = Math.ceil(blockHeight / (gridCellHeight + borderWidth * 0.5));
                var endMinutes = startMinutes + (rowSpan * timeInterval);
                
                startTime = minutesToTime(startMinutes);
                endTime = minutesToTime(endMinutes);
                duration = endMinutes - startMinutes;
            }

            // Извлекаем данные из содержимого блока
            var subject = lines[0] || '';  // Первая строка - название предмета
            var teacher = lines[1] || '';  // Вторая строка - преподаватель
            var students = lines[2] || ''; // Третья строка - группа студентов
            
            // Получаем цвет блока
            var blockColor = window.getComputedStyle(block).backgroundColor;
            // Преобразуем в HEX формат
            var hexColor = rgbToHex(blockColor);
            
            // Создаем запись активности для экспорта
            var activity = {
                subject: subject,
                students: students,
                teacher: teacher,
                room: roomName,
                room_display: roomDisplay,
                building: building,
                day: day,
                start_time: startTime,  // Строка в формате "HH:MM"
                end_time: endTime,      // Строка в формате "HH:MM"
                duration: duration,
                color: hexColor
            };
            
            // Добавляем активность в общий список
            scheduleData.push(activity);
        });
    });
    
    return scheduleData;
}

// Вспомогательная функция преобразования минут в формат времени HH:MM
function minutesToTime(minutes) {
    var hours = Math.floor(minutes / 60);
    var mins = minutes % 60;
    return hours.toString().padStart(2, '0') + ':' + mins.toString().padStart(2, '0');
}

// Вспомогательная функция для преобразования RGB в HEX
function rgbToHex(rgb) {
    // Если это уже HEX
    if (rgb.startsWith('#')) {
        return rgb;
    }
    
    // Если это RGB
    var rgbMatch = rgb.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (rgbMatch) {
        var r = parseInt(rgbMatch[1]);
        var g = parseInt(rgbMatch[2]);
        var b = parseInt(rgbMatch[3]);
        return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }
    
    // Если это RGBA
    var rgbaMatch = rgb.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([0-9.]+)\)/);
    if (rgbaMatch) {
        var r = parseInt(rgbaMatch[1]);
        var g = parseInt(rgbaMatch[2]);
        var b = parseInt(rgbaMatch[3]);
        return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }
    
    // Если формат не распознан
    return '#CCCCCC';
}

// Функция проверки доступности сервера
function checkServerAvailability(callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', 'http://localhost:5000/', true);
    xhr.timeout = 2000; // 2 секунды на ответ
    
    xhr.onload = function() {
        if (xhr.status === 200) {
            console.log('Сервер доступен');
            callback(true);
        } else {
            console.error('Сервер недоступен, статус:', xhr.status);
            callback(false);
        }
    };
    
    xhr.ontimeout = function() {
        console.error('Таймаут при проверке сервера');
        callback(false);
    };
    
    xhr.onerror = function() {
        console.error('Ошибка при проверке сервера');
        callback(false);
    };
    
    xhr.send();
}

// Функция для показа диалога подтверждения экспорта
function showExportConfirmation(callback) {
    // Создаем модальное окно
    var modal = document.createElement('div');
    modal.id = 'exportConfirmModal';
    modal.style.position = 'fixed';
    modal.style.top = '0';
    modal.style.left = '0';
    modal.style.width = '100%';
    modal.style.height = '100%';
    modal.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
    modal.style.zIndex = '10000';
    modal.style.display = 'flex';
    modal.style.justifyContent = 'center';
    modal.style.alignItems = 'center';
    
    var modalContent = document.createElement('div');
    modalContent.style.backgroundColor = 'white';
    modalContent.style.padding = '20px';
    modalContent.style.borderRadius = '10px';
    modalContent.style.boxShadow = '0 4px 10px rgba(0, 0, 0, 0.3)';
    modalContent.style.maxWidth = '500px';
    modalContent.style.width = '90%';
    modalContent.style.textAlign = 'center';
    
    modalContent.innerHTML = `
        <div style="margin-bottom: 20px;">
            <div style="font-size: 30px; color: #f39c12; margin-bottom: 10px;">⚠️</div>
            <h3 style="margin: 0 0 10px 0; color: #333;">Внимание!</h3>
            <p style="margin: 0; color: #666; line-height: 1.5;">
                При экспорте в Excel будут сохранены данные только из <strong>видимых столбцов</strong> расписания.
            </p>
            <p style="margin: 10px 0 0 0; color: #666; line-height: 1.5; font-size: 14px;">
                Убедитесь, что все нужные столбцы отображаются в таблице перед экспортом.
            </p>
        </div>
        <div style="display: flex; gap: 10px; justify-content: center;">
            <button id="confirmExport" style="
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
            ">Продолжить экспорт</button>
            <button id="cancelExport" style="
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
            ">Отмена</button>
        </div>
    `;
    
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // Добавляем стили при наведении
    var confirmBtn = modalContent.querySelector('#confirmExport');
    var cancelBtn = modalContent.querySelector('#cancelExport');
    
    confirmBtn.addEventListener('mouseenter', function() {
        this.style.backgroundColor = '#218838';
    });
    confirmBtn.addEventListener('mouseleave', function() {
        this.style.backgroundColor = '#28a745';
    });
    
    cancelBtn.addEventListener('mouseenter', function() {
        this.style.backgroundColor = '#c82333';
    });
    cancelBtn.addEventListener('mouseleave', function() {
        this.style.backgroundColor = '#dc3545';
    });
    
    // Обработчики кнопок
    confirmBtn.addEventListener('click', function() {
        document.body.removeChild(modal);
        callback(true);
    });
    
    cancelBtn.addEventListener('click', function() {
        document.body.removeChild(modal);
        callback(false);
    });
    
    // Закрытие по Esc
    document.addEventListener('keydown', function escHandler(event) {
        if (event.key === 'Escape') {
            document.body.removeChild(modal);
            callback(false);
            document.removeEventListener('keydown', escHandler);
        }
    });
    
    // Закрытие по клику вне модального окна
    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            document.body.removeChild(modal);
            callback(false);
        }
    });
}

// Инициализация экспорта в Excel
function initExcelExport() {
    // Находим кнопку экспорта
    var exportButton = document.getElementById('exportToExcel');
    if (exportButton) {
        // Очищаем старые обработчики событий путем клонирования элемента
        var newExportButton = exportButton.cloneNode(true);
        exportButton.parentNode.replaceChild(newExportButton, exportButton);
        exportButton = newExportButton;
        
        // Добавляем обработчик клика на кнопку
        exportButton.addEventListener('click', function() {
            // Показываем диалог подтверждения
            showExportConfirmation(function(confirmed) {
                if (confirmed) {
                    exportScheduleToExcel();
                }
            });
        });
        console.log('Инициализирован обработчик экспорта в Excel');
    } else {
        console.error('Кнопка exportToExcel не найдена');
    }
}

// Основная функция экспорта расписания в Excel
function exportScheduleToExcel() {
    try {
        console.log('Начинаем сбор данных для экспорта в Excel...');
        
        // Проверяем доступность сервера перед сбором данных
        checkServerAvailability(function(isAvailable) {
            if (!isAvailable) {
                showExportProgress('Сервер экспорта недоступен!', true);
                checkServerAndAdvise();
                return;
            }
            
            // Собираем данные расписания
            var scheduleData = collectScheduleData();
            console.log('Собрано записей: ' + scheduleData.length);
            
            // Показываем индикатор процесса
            showExportProgress('Подготовка данных для экспорта...');
            
            // Получаем CSRF-токен для безопасности
            var csrfToken = document.getElementById('csrf_token')?.value || '';
            
            // Вместо формы используем XMLHttpRequest для прямой отправки и получения ответа
            var xhr = new XMLHttpRequest();
            xhr.open('POST', 'http://localhost:5000/export_to_excel', true);
            
            // Обработка успешного завершения запроса
            xhr.onload = function() {
                if (xhr.status === 200) {
                    console.log('Получен ответ от сервера');
                    // Создаем временную ссылку для скачивания файла
                    var blob = new Blob([xhr.response], { 
                        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
                    });
                    var link = document.createElement('a');
                    link.href = window.URL.createObjectURL(blob);
                    link.download = 'schedule_export.xlsx';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(link.href);
                    
                    // Скрываем индикатор прогресса
                    hideExportProgress();
                    showExportProgress('Excel-файл успешно скачан!', true);
                    // Автоматическое закрытие через 2 секунды (оставляем возможность закрыть вручную)
                    setTimeout(function() {
                        // Проверяем, не закрыл ли пользователь сообщение сам
                        if (document.getElementById('exportProgress') && 
                            document.getElementById('exportProgress').style.display !== 'none') {
                            hideExportProgress();
                        }
                    }, 2000);
                } else {
                    console.error('Ошибка при получении файла:', xhr.status, xhr.statusText);
                    hideExportProgress();
                    showExportProgress('Ошибка при получении файла: ' + xhr.statusText, true);
                }
            };
            
            // Обработка ошибок сети
            xhr.onerror = function() {
                console.error('Ошибка сети при отправке запроса');
                hideExportProgress();
                showExportProgress('Ошибка сети! Сервер недоступен.', true);
                
                // Проверяем доступность сервера и даем рекомендации
                checkServerAndAdvise();
            };
            
            // Указываем, что нам нужен ответ в виде бинарных данных
            xhr.responseType = 'arraybuffer';
            
            // Устанавливаем заголовки запроса
            xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
            
            // Формируем данные запроса
            var formData = 'schedule_data=' + encodeURIComponent(JSON.stringify(scheduleData)) + 
                          '&csrf_token=' + encodeURIComponent(csrfToken);
            
            // Отправляем запрос
            xhr.send(formData);
            
            console.log('Данные отправлены для создания Excel-файла');
        });
    } catch (error) {
        console.error('Ошибка при экспорте в Excel:', error);
        hideExportProgress();
        showExportProgress('Ошибка при экспорте: ' + error.message, true);
    }
}

// Функция-обработчик нажатия клавиши Esc
function handleEscapeKey(event) {
    if (event.key === 'Escape') {
        hideExportProgress();
        // Удаляем обработчик после закрытия, чтобы не накапливались
        document.removeEventListener('keydown', handleEscapeKey);
    }
}

// Функция для скрытия индикатора процесса экспорта
function hideExportProgress() {
    var progressDiv = document.getElementById('exportProgress');
    if (progressDiv) {
        progressDiv.style.display = 'none';
        // Удаляем обработчик Esc при закрытии
        document.removeEventListener('keydown', handleEscapeKey);
    }
}

// Функция для отображения индикатора процесса экспорта
function showExportProgress(message, isResult) {
    // Проверяем, существует ли уже индикатор
    if (document.getElementById('exportProgress')) {
        var messageBox = document.getElementById('exportProgress').querySelector('div');
        if (messageBox) {
            // Если это результат операции, добавляем кнопку закрытия
            if (isResult) {
                messageBox.innerHTML = `
                    <p style="margin: 0; text-align: center; position: relative; ${isResult ? 'color: green; font-weight: bold;' : ''}">
                        ${message}
                        <button onclick="hideExportProgress()" style="position: absolute; top: -5px; right: -5px; border: none; background: none; font-size: 20px; font-weight: bold; color: #555; cursor: pointer;" title="Закрыть сообщение">×</button>
                    </p>
                `;
                // Добавляем обработчик Esc
                document.addEventListener('keydown', handleEscapeKey);
            } else {
                messageBox.innerHTML = `<p style="margin: 0; text-align: center;">${message}</p>`;
            }
            document.getElementById('exportProgress').style.display = 'flex';
        }
        return;
    }
    
    // Создаем индикатор прогресса
    var progressDiv = document.createElement('div');
    progressDiv.id = 'exportProgress';
    progressDiv.style.position = 'fixed';
    progressDiv.style.top = '0';
    progressDiv.style.left = '0';
    progressDiv.style.width = '100%';
    progressDiv.style.height = '100%';
    progressDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
    progressDiv.style.zIndex = '10000';
    progressDiv.style.display = 'flex';
    progressDiv.style.justifyContent = 'center';
    progressDiv.style.alignItems = 'center';
    
    var messageBox = document.createElement('div');
    messageBox.style.backgroundColor = 'white';
    messageBox.style.padding = '20px';
    messageBox.style.borderRadius = '5px';
    messageBox.style.boxShadow = '0 0 10px rgba(0, 0, 0, 0.3)';
    messageBox.style.maxWidth = '80%';
    
    // Если это результат операции, добавляем кнопку закрытия
    if (isResult) {
        messageBox.innerHTML = `
            <p style="margin: 0; text-align: center; position: relative; ${isResult ? 'color: green; font-weight: bold;' : ''}">
                ${message}
                <button onclick="hideExportProgress()" style="position: absolute; top: -5px; right: -5px; border: none; background: none; font-size: 20px; font-weight: bold; color: #555; cursor: pointer;" title="Закрыть сообщение">×</button>
            </p>
        `;
        // Добавляем обработчик Esc
        document.addEventListener('keydown', handleEscapeKey);
    } else {
        messageBox.innerHTML = `<p style="margin: 0; text-align: center;">${message}</p>`;
    }
    
    progressDiv.appendChild(messageBox);
    document.body.appendChild(progressDiv);
}

// Функция проверки доступности сервера и вывода рекомендаций
function checkServerAndAdvise() {
    var message = document.createElement('div');
    message.style.backgroundColor = '#f8f8f8';
    message.style.border = '1px solid #ddd';
    message.style.borderRadius = '5px';
    message.style.padding = '15px';
    message.style.margin = '10px 0';
    message.style.fontSize = '14px';
    message.style.lineHeight = '1.5';
    message.style.color = '#333';
    message.style.position = 'relative'; // Для позиционирования кнопки закрытия
    
    // Добавляем кнопку закрытия
    var closeButton = document.createElement('button');
    closeButton.innerHTML = '×';
    closeButton.style.position = 'absolute';
    closeButton.style.top = '5px';
    closeButton.style.right = '5px';
    closeButton.style.border = 'none';
    closeButton.style.background = 'none';
    closeButton.style.fontSize = '20px';
    closeButton.style.fontWeight = 'bold';
    closeButton.style.color = '#d9534f';
    closeButton.style.cursor = 'pointer';
    closeButton.title = 'Закрыть сообщение';
    closeButton.onclick = hideExportProgress;
    
    message.appendChild(closeButton);
    
    message.innerHTML += `
        <h4 style="margin-top: 0; color: #d9534f;">Сервер экспорта недоступен!</h4>
        <p>Возможные причины и решения:</p>
        <ol>
            <li>Flask-сервер не запущен. Запустите <code>server_routes.py</code> вручную.</li>
            <li>Порт 5000 занят другим приложением. Измените порт в <code>server_routes.py</code>.</li>
            <li>Брандмауэр блокирует соединение. Проверьте настройки брандмауэра.</li>
        </ol>
        <p>Для запуска сервера выполните в командной строке:</p>
        <pre style="background: #eee; padding: 5px;">python server_routes.py</pre>
        <p style="margin-top: 10px; text-align: center; font-style: italic; color: #666;">
            Нажмите ESC или кнопку × чтобы закрыть это сообщение
        </p>
    `;
    
    var progressDiv = document.getElementById('exportProgress');
    if (progressDiv) {
        var messageBox = progressDiv.querySelector('div');
        if (messageBox) {
            messageBox.appendChild(message);
        }
    }
    
    // Добавляем обработчик нажатия клавиши Esc
    document.addEventListener('keydown', handleEscapeKey);
}