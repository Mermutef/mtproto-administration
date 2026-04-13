function linkFormatter(value, row) {
    return `<button class="btn btn-sm btn-primary copy-link-btn" data-link="${row.link}"><i class="bi bi-clipboard"></i> Копировать</button>`;
}

function actionFormatter(value, row) {
    return `
        <div class="action-buttons">
            <button class="btn btn-sm btn-secondary rename-btn" onclick="renameUser('${row.username}')">
                <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-danger delete-btn" onclick="deleteUser('${row.username}')">
                <i class="bi bi-trash"></i>
            </button>
        </div>
    `;
}

function statusFormatter(value, row) {
    const statusMap = {
        "pending": '<span class="badge bg-secondary">Ожидает</span>',
        "approved": '<span class="badge bg-primary">Одобрена</span>',
        "rejected": '<span class="badge bg-danger">Отклонена</span>',
        "revoked": '<span class="badge bg-danger">Отозвана</span>',
        "—": '<span class="badge bg-warning">Неизвестно</span>'
    };
    return statusMap[value] || value;
}

function tgIDFormatter(value, row) {
    const statusMap = {
        "web": '<span class="badge bg-secondary">Web</span>',
        "unknown": '<span class="badge bg-warning">Неизвестно</span>',
        "—": '<span class="badge bg-warning">Неизвестно</span>',
    };
    return statusMap[value] || `<span class="badge bg-primary">${value}</span>`;
}

$(document).on('click', '.copy-link-btn', function () {
    const link = $(this).data('link');
    copyToClipboard(link);
});

$('#submitAddUser').click(function () {
    const username = $('#newUsername').val().trim();
    if (!username) {
        showToast('Введите логин', 'danger');
        return;
    }
    $.ajax({
        url: '/api/add_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({username: username}),
        success: function (res) {
            if (res.success) {
                $('#addUserModal').modal('hide');
                $('#newUsername').val('');
                $('#users-table').bootstrapTable('refresh');
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
    const username = $('#sendToUsername').val().trim();
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

$('#restartContainerBtn').click(function (e) {
    e.preventDefault();
    $('#confirmRestartContainerModal').modal('show');
});

$('#confirmRestartContainer').click(function () {
    $('#confirmRestartContainerModal').modal('hide');
    $.ajax({
        url: '/api/restart_container',
        method: 'POST',
        success: function (res) {
            showToast(res.message, 'success');
        },
        error: function () {
            showToast('Ошибка перезапуска', 'danger');
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

function refreshTable() {
    $('#users-table').bootstrapTable('refresh');
}