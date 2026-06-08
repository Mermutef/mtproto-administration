function linkFormatter(value, row) {
    return `<button class="btn btn-sm btn-primary copy-link-btn" data-link="${row.link}"><i class="bi bi-clipboard"></i> Копировать</button>`;
}

function actionFormatter(value, row) {
    return `
        <div class="action-buttons">
            <button class="btn btn-sm btn-secondary rename-btn" onclick="renameUser('${row.email}')">
                <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-danger delete-btn" onclick="deleteUser('${row.email}')">
                <i class="bi bi-trash"></i>
            </button>
        </div>
    `;
}

function statusFormatter(value, row) {
    return value ? '<span class="badge bg-primary">Активен</span>' : '<span class="badge bg-danger">Отключен</span>';
}

function emailFormatter(value, row) {
    if (!value) return '';
    return `<a href="#" onclick="openSendToModal('${value}', '${row.telegram_id}'); return false;" class="text-decoration-none">${value}</a>`;
}

$(document).on('click', '.copy-link-btn', function () {
    const link = $(this).data('link');
    copyToClipboard(link);
});

$('#submitAddUser').click(function () {
    const email = $('#newUsername').val().trim();
    if (!email) {
        showToast('Введите email', 'danger');
        return;
    }
    $.ajax({
        url: '/api/trojan/add_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({email: email}),
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

window.deleteUser = function (email) {
    $('#deleteUsernamePlaceholder').text(email);
    $('#deleteUsernameInput').val(email);
    $('#confirmDeleteUserModal').modal('show');
};

$('#confirmDeleteUserBtn').click(function () {
    const email = $('#deleteUsernameInput').val();
    $('#confirmDeleteUserModal').modal('hide');
    $.ajax({
        url: '/api/trojan/delete_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({email: email}),
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

window.renameUser = function (email) {
    $('#renameOldName').val(email);
    $('#renameNewName').val('');
    $('#renameModal').modal('show');
};

$('#submitRename').click(function () {
    const oldEmail = $('#renameOldName').val();
    const newEmail = $('#renameNewName').val().trim();
    if (!newEmail) {
        showToast('Введите новый логин', 'danger');
        return;
    }
    $.ajax({
        url: '/api/trojan/rename_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({old_email: oldEmail, new_email: newEmail}),
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
