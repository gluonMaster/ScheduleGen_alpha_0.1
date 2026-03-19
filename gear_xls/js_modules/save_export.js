// Module for saving and exporting the schedule

function getServerBaseUrl() {
    return '';
}

function _saveIntermediateViaServer(htmlContent, filename, onResult) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', getServerBaseUrl() + '/save_intermediate', true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onload = function() {
        var resp;
        try {
            resp = JSON.parse(xhr.responseText);
        } catch (e) {
            onResult({ success: false, reason: 'invalid_response', status: xhr.status });
            return;
        }

        if (xhr.status >= 200 && xhr.status < 300) {
            onResult(resp);
            return;
        }

        resp.success = false;
        resp.status = xhr.status;
        if (!resp.reason) {
            resp.reason = 'http_' + xhr.status;
        }
        onResult(resp);
    };

    xhr.onerror = function() {
        onResult({ success: false, reason: 'network_error' });
    };

    xhr.send(JSON.stringify({
        html_content: htmlContent,
        default_filename: filename
    }));
}

function _saveIntermediateFallback(htmlContent, filename) {
    var blob = new Blob([htmlContent], { type: 'text/html' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    alert('Сервер недоступен. Файл скачан в папку загрузок браузера.');
}

// Initialization of save functions
function initSaveExport() {
    // Get buttons
    var saveScheduleButton = document.getElementById('saveSchedule');
    var saveIntermediateButton = document.getElementById('saveIntermediate');
    
    // Clear old event handlers by cloning elements
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
    
    // Handler for final save: saves a static version (without drag & drop)
    if (saveScheduleButton) {
        saveScheduleButton.addEventListener('click', function() {
            // Add class to mark the page as final
            document.body.classList.add('static-schedule');
            // Disable drag & drop interactivity
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

    // Handler for intermediate save (interactivity remains)
    if (saveIntermediateButton) {
        saveIntermediateButton.addEventListener('click', function() {
            var defaultName = 'intermediate_schedule.html';
            var htmlContent = document.documentElement.outerHTML;

            // Try native save dialog via Flask; fall back to blob download if unavailable
            var serverCheckXhr = new XMLHttpRequest();
            serverCheckXhr.open('GET', getServerBaseUrl() + '/', true);
            serverCheckXhr.timeout = 2000;

            serverCheckXhr.onload = function() {
                if (serverCheckXhr.status === 200) {
                    _saveIntermediateViaServer(htmlContent, defaultName, function(result) {
                        if (result.success) {
                            alert('Файл сохранён: ' + result.path);
                        } else if (result.reason === 'cancelled') {
                            // User cancelled the dialog — do nothing
                        } else if (
                            result.reason === 'network_error' ||
                            result.reason === 'invalid_response' ||
                            result.reason === 'http_404' ||
                            (typeof result.status === 'number' && result.status >= 500)
                        ) {
                            _saveIntermediateFallback(htmlContent, defaultName);
                        } else {
                            alert('Ошибка при сохранении: ' + (result.reason || 'неизвестная ошибка'));
                        }
                    });
                } else {
                    _saveIntermediateFallback(htmlContent, defaultName);
                }
            };

            serverCheckXhr.onerror = function() {
                _saveIntermediateFallback(htmlContent, defaultName);
            };

            serverCheckXhr.ontimeout = function() {
                _saveIntermediateFallback(htmlContent, defaultName);
            };

            serverCheckXhr.send();
        });
    }
}
