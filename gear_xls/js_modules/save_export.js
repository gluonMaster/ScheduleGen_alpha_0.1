// Модуль для сохранения и экспорта расписания

// Инициализация функций сохранения
function initSaveExport() {
    // Получаем кнопки
    var saveScheduleButton = document.getElementById('saveSchedule');
    var saveIntermediateButton = document.getElementById('saveIntermediate');
    
    // Очищаем старые обработчики событий путем клонирования элементов
    if (saveScheduleButton) {
        var newSaveScheduleButton = saveScheduleButton.cloneNode(true);
        saveScheduleButton.parentNode.replaceChild(newSaveScheduleButton, saveScheduleButton);
        saveScheduleButton = newSaveScheduleButton;
    }
    
    if (saveIntermediateButton) {
        var newSaveIntermediateButton = saveIntermediateButton.cloneNode(true);
        saveIntermediateButton.parentNode.replaceChild(newSaveIntermediateButton, saveIntermediateButton);
        saveIntermediateButton = newSaveIntermediateButton;
    }
    
    // Обработчик для финального сохранения – сохраняется статичная версия (без drag & drop)
    if (saveScheduleButton) {
        saveScheduleButton.addEventListener('click', function() {
            // Добавляем класс, чтобы пометить страницу как финальную
            document.body.classList.add('static-schedule');
            // Отключаем интерактивность drag & drop (например, изменяем курсор)
            document.querySelectorAll('.activity-block').forEach(function(block) {
                block.style.cursor = 'default';
            });
            var htmlContent = document.documentElement.outerHTML;
            var blob = new Blob([htmlContent], {type: 'text/html'});
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'final_schedule.html';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            alert('Финальная версия расписания сохранена.');
        });
    }

    // Обработчик для промежуточного сохранения (интерактивность сохраняется)
    if (saveIntermediateButton) {
        saveIntermediateButton.addEventListener('click', function() {
            // Запрашиваем имя файла у пользователя
            var filename = prompt("Введите имя файла для сохранения", "intermediate_schedule.html");
            if (!filename) return;  // если пользователь отменил, ничего не делаем

            // Здесь не отключаем интерактивность — сохраняется текущее состояние страницы со скриптами
            var htmlContent = document.documentElement.outerHTML;
            var blob = new Blob([htmlContent], {type: 'text/html'});
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            alert("Промежуточная версия расписания сохранена.");
        });
    }
}
