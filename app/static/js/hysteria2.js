function linkFormatter(value, row) {
    return `<button class="btn btn-sm btn-primary copy-link-btn" data-link="${row.link}"><i class="bi bi-clipboard"></i> Копировать</button>`;
}

function actionFormatter(value, row) {
    return `
        <div class="action-buttons">
            <button class="btn btn-sm btn-danger delete-btn" onclick="deleteUser('${row.name}')">
                <i class="bi bi-trash"></i>
            </button>
        </div>
    `;
}

function statusFormatter(value, row) {
    return value ? '<span class="badge bg-primary">Активен</span>' : '<span class="badge bg-danger">Отключен</span>';
}

$(document).on('click', '.copy-link-btn', function () {
    const link = $(this).data('link');
    copyToClipboard(link);
});

$('#submitAddUser').click(function () {
    const name = $('#newUsername').val().trim();
    if (!name) {
        showToast('Введите имя пользователя', 'danger');
        return;
    }
    $.ajax({
        url: '/api/hysteria2/add_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({name: name}),
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

window.deleteUser = function (name) {
    $('#deleteUsernamePlaceholder').text(name);
    $('#deleteUsernameInput').val(name);
    $('#confirmDeleteUserModal').modal('show');
};

$('#confirmDeleteUserBtn').click(function () {
    const name = $('#deleteUsernameInput').val();
    $('#confirmDeleteUserModal').modal('hide');
    $.ajax({
        url: '/api/hysteria2/delete_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({name: name}),
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