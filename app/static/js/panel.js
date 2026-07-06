/* OurAdmin unified panel */

let currentTab = 'users';

/* ── Tab switching ──────────────────────────────────────────────── */

function showTab(name) {
    currentTab = name;
    // Hide all tab contents
    document.querySelectorAll('#tab-users, #tab-requests, #tab-broadcast').forEach(el => {
        if (el) el.classList.add('d-none');
    });
    // Highlight active nav link
    document.querySelectorAll('.navbar .nav-link').forEach(el => el.classList.remove('active'));
    const navEl = document.getElementById(`nav-${name}`);
    if (navEl) navEl.classList.add('active');

    // Show selected tab
    const tabEl = document.getElementById(`tab-${name}`);
    if (tabEl) tabEl.classList.remove('d-none');

    if (name === 'users') loadUsersTable();
    if (name === 'requests') loadRequests();
    if (name === 'broadcast') loadBroadcast();
}

/* ── Users table ────────────────────────────────────────────────── */

function loadUsersTable() {
    $.getJSON('/api/panel/users/all', function (users) {
        $('#users-table').bootstrapTable('load', users);
    }).fail(function () {
        showToast('Ошибка загрузки пользователей', 'danger');
    });
}

/* ── Protocol toggle ────────────────────────────────────────────── */

function toggleProtocol(username, proto) {
    const $cb = $(event.target);
    const enable = $cb.prop('checked');
    $.ajax({
        url: `/api/panel/${proto}/toggle`,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({username: username, enable: enable}),
        success: function (data) {
            if (data.success) {
                showToast(`${proto.toUpperCase()}: ${data.message || 'OK'}`, 'success');
                loadUsersTable();
            } else {
                showToast(data.error || 'Ошибка', 'danger');
                loadUsersTable();
            }
        },
        error: function (xhr) {
            showToast(xhr.responseJSON?.error || 'Ошибка', 'danger');
            loadUsersTable();
        },
    });
}

/* ── Add user ───────────────────────────────────────────────────── */

$('#submitAddUserBtn').on('click', function () {
    const username = $('#newUsername').val().trim();
    if (!username) {
        showToast('Введите логин', 'danger');
        return;
    }
    $.ajax({
        url: '/api/panel/add_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            username: username,
            protocols: ['mtproto'],
        }),
        success: function (data) {
            if (data.success) {
                $('#addUserModal').modal('hide');
                $('#newUsername').val('');
                loadUsersTable();
                showToast('Пользователь добавлен', 'success');
            } else {
                showToast(data.error || 'Ошибка', 'danger');
            }
        },
        error: function (xhr) {
            showToast(xhr.responseJSON?.error || 'Ошибка', 'danger');
        },
    });
});

/* ── Requests ──────────────────────────────────────────────────── */

function loadRequests() {
    const el = document.querySelector('#tab-requests .card-body');
    if (!el) return;
    $.getJSON('/api/panel/requests', function (data) {
        let html = '';
        const reqs = data.requests || [];
        if (!reqs.length) {
            html = '<div class="text-center py-5 text-muted">Нет заявок</div>';
        } else {
            reqs.forEach(r => {
                html += `<div class="d-flex justify-content-between align-items-center p-2 border-bottom">
                    <div><strong>${r.user_name}</strong> (${r.protocol}) — ${r.status}</div>
                    <div><small>${r.created_at}</small></div>
                </div>`;
            });
        }
        el.innerHTML = html;
    });
}

function loadBroadcast() {
    const el = document.querySelector('#tab-broadcast .card-body');
    if (!el) return;
    el.innerHTML = ` 
        <form id="broadcast-form">
            <div class="mb-3">
                <label class="form-label">Текст сообщения</label>
                <textarea class="form-control" rows="3" id="broadcast-msg"></textarea>
            </div>
            <button class="btn btn-primary" type="submit">Отправить</button>
        </form>
    `;

    $('#broadcast-form').on('submit', function (e) {
        e.preventDefault();
        const msg = $('#broadcast-msg').val().trim();
        if (!msg) return showToast('Введите текст', 'danger');
        $.post('/api/broadcast', JSON.stringify({message: msg}))
            .done(function (r) { showToast(r.message || 'Ок', 'success'); })
            .fail(function (x) { showToast(x.responseJSON?.error || 'Ошибка', 'danger'); });
    });
}

/* ── Formatters ─────────────────────────────────────────────────── */

function protocolsFormatter(value, row) {
    const protos = ['mtproto', 'xray', 'trojan', 'hysteria2'];
    const icons = {mtproto: '🛡️', xray: '🌐', trojan: '🐴', hysteria2: '⚡'};
    const ident = row.username || row.email || '';
    return protos.map(p => {
        const has = row.protocols && row.protocols[p];
        return `<label class="toggle-switch me-1" title="${p}">
            <input type="checkbox" ${has ? 'checked' : ''} onchange="toggleProtocol('${ident}', '${p}')">
            <span class="slider">${icons[p]}</span>
        </label>`;
    }).join('');
}

function tgIDFormatter(value, row) {
    if (!value || value === '—' || value === 'unknown') return '<span class="badge bg-warning">Неизвестно</span>';
    if (value === 'web') return '<span class="badge bg-secondary">Web</span>';
    return `<span class="badge bg-primary">${value}</span>`;
}

function dateFormatter(value) {
    if (!value || value === '—') return '—';
    try {
        const d = new Date(value);
        if (isNaN(d.getTime())) return value;
        const pad = n => String(n).padStart(2, '0');
        return `${pad(d.getDate())}.${pad(d.getMonth()+1)}.${d.getFullYear()}`;
    } catch { return value; }
}

function actionsFormatter(value, row) {
    const ident = row.username || row.email || '';
    return `
        <button class="btn btn-sm btn-outline-primary me-1" onclick="showUserDetail('${ident}')" title="Подробнее">
            <i class="bi bi-info-circle"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteUser('${ident}')" title="Удалить">
            <i class="bi bi-trash"></i>
        </button>`;
}

/* ── Detail modal ───────────────────────────────────────────────── */

function showUserDetail(identifier) {
    $.getJSON(`/api/panel/user/${identifier}`, function (user) {
        const html = `
            <p><strong>Логин:</strong> ${user.username || user.email}</p>
            <p><strong>TG ID:</strong> ${user.telegram_id || '—'}</p>
            <p><strong>UUID:</strong> ${user.uuid || '—'}</p>
            <p><strong>Подписка:</strong> ${user.link ? `<a href="${user.link}" target="_blank">${user.link}</a>` : '—'}</p>
        `;
        const el = document.querySelector('#detailModal .modal-body');
        if (el) el.innerHTML = html;
        $('#detailModal').modal('show');
    }).fail(function () {
        showToast('Ошибка загрузки', 'danger');
    });
}

function deleteUser(identifier) {
    if (!confirm(`Удалить ${identifier}?`)) return;
    $.ajax({
        url: '/api/panel/delete_user',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({username: identifier}),
        success: function (data) {
            if (data.success) {
                loadUsersTable();
                showToast('Удалён', 'success');
            } else {
                showToast(data.error || 'Ошибка', 'danger');
            }
        },
        error: function (xhr) {
            showToast(xhr.responseJSON?.error || 'Ошибка', 'danger');
        },
    });
}

/* ── Toast ──────────────────────────────────────────────────────── */

function showToast(message, type) {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0`;
    toast.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
    toastContainer.appendChild(toast);
    new bootstrap.Toast(toast, {delay: 3000}).show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

/* ── Init ───────────────────────────────────────────────────────── */

$(function () {
    showTab('users');
});
