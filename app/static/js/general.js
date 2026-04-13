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
    const bsToast = new bootstrap.Toast(toast, {delay: 2000});
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Ссылка скопирована!', 'success');
    }).catch(() => {
        showToast('Ошибка копирования', 'danger');
    });
}

function dateFormatter(value, row) {
    if (!value || value === '—') return '—';
    try {
        const date = new Date(value);
        if (isNaN(date.getTime())) return value; // fallback
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