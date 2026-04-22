function showToast(message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, {delay: 3000});
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

function usernameFormatter(value, row) {
    if (!value) return '';
    return `<a href="#" onclick="openSendToModal('${value}', '${row.telegram_id}'); return false;" class="text-decoration-none">${value}</a>`;
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Скопировано в буфер обмена', 'success');
    }).catch(() => {
        showToast('Ошибка копирования', 'danger');
    });
}

function dateFormatter(value, row) {
    if (!value || value === '—') return '—';
    try {
        const date = new Date(value);
        if (isNaN(date.getTime())) return value;
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const year = date.getFullYear();
        return `${hours}:${minutes} ${day}.${month}.${year}`;
    } catch (e) {
        return value;
    }
}

function dateSorter(a, b, rowA, rowB) {
    const dateA = rowA.created_at ? new Date(rowA.created_at) : new Date(0);
    const dateB = rowB.created_at ? new Date(rowB.created_at) : new Date(0);
    if (isNaN(dateA)) return -1;
    if (isNaN(dateB)) return 1;
    return dateA - dateB;
}

function tgIDFormatter(value, row) {
    if (!value || value === '—' || value === 'unknown') {
        return '<span class="badge bg-warning">Неизвестно</span>';
    }
    if (value === 'web') {
        return '<span class="badge bg-secondary">Web</span>';
    }
    return `<span class="badge bg-primary text-decoration-none">${value}</span>`;
}

// Новая функция для открытия модального окна сообщения пользователю
function openSendToModal(username, tgId) {
    if (!tgId || tgId === '—' || tgId === 'unknown' || tgId === 'web') {
        showToast('У этого пользователя нет Telegram ID. Отправить сообщение невозможно.', 'danger');
        return;
    }
    $('#sendToUsername').val(username);
    $('#sendToUsernameDisplay').val(username);
    $('#sendToMessage').val('');
    $('#sendToModal').modal('show');
}

$(document).ready(function () {
    // Кнопка "Новый пользователь" в навбаре открывает модалку; логика submit зависит от текущего протокола
    // (определяется в соответствующем JS-файле)

    $('#submitBroadcast').click(function () {
        const message = $('#broadcastMessage').val().trim();
        if (!message) {
            showToast('Введите текст сообщения', 'danger');
            return;
        }
        $.ajax({
            url: '/api/broadcast',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({message: message}),
            success: function (res) {
                if (res.success) {
                    $('#broadcastModal').modal('hide');
                    $('#broadcastMessage').val('');
                    showToast(res.message, 'success');
                } else {
                    showToast(res.error, 'danger');
                }
            },
            error: function (xhr) {
                showToast(xhr.responseJSON?.error || 'Ошибка', 'danger');
            }
        });
    });

    $('#submitSendTo').click(function () {
        const username = $('#sendToUsername').val();
        const message = $('#sendToMessage').val().trim();
        if (!username || !message) {
            showToast('Заполните оба поля', 'danger');
            return;
        }
        $.ajax({
            url: '/api/send_to',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({username: username, message: message}),
            success: function (res) {
                if (res.success) {
                    $('#sendToModal').modal('hide');
                    $('#sendToUsername').val('');
                    $('#sendToMessage').val('');
                    showToast(res.message, 'success');
                } else {
                    showToast(res.error, 'danger');
                }
            },
            error: function (xhr) {
                showToast(xhr.responseJSON?.error || 'Ошибка', 'danger');
            }
        });
    });

    $('#restartServerBtn').click(function (e) {
        e.preventDefault();
        $('#confirmRestartServerModal').modal('show');
    });

    $('#confirmRestartServer').click(function () {
        $('#confirmRestartServerModal').modal('hide');
        $.ajax({
            url: '/api/restart_server',
            method: 'POST',
            success: function (res) {
                alert(res.message);
            },
            error: function () {
                alert('Ошибка при перезагрузке сервера');
            }
        });
    });
});