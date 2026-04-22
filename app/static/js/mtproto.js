// Форматтеры для таблицы MTProto
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
        url: '/api/mtproto/add_user',
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

window.renameUser = function (username) {
    $('#renameOldName').val(username);
    $('#renameNewName').val('');
    $('#renameModal').modal('show');
};

$('#submitRename').click(function () {
    const oldName = $('#renameOldName').val();
    const newName = $('#renameNewName').val().trim();
    if (!newName) {
        showToast('Введите новое имя', 'danger');
        return;
    }
    $.ajax({
        url: '/api/mtproto/rename_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({old_name: oldName, new_name: newName}),
        success: function (res) {
            if (res.success) {
                $('#renameModal').modal('hide');
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

window.deleteUser = function (username) {
    $('#deleteUsernamePlaceholder').text(username);
    $('#deleteUsernameInput').val(username);
    $('#confirmDeleteUserModal').modal('show');
};

$('#confirmDeleteUserBtn').click(function () {
    const username = $('#deleteUsernameInput').val();
    $('#confirmDeleteUserModal').modal('hide');
    $.ajax({
        url: '/api/mtproto/delete_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({username: username}),
        success: function (res) {
            if (res.success) {
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