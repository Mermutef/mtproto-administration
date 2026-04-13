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
        url: '/api/rename_user',
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
        url: '/api/delete_user',
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
