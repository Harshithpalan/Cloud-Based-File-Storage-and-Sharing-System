/**
 * Cloud File Share — Core Client Interaction Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    initDropzone();
    initFlashAutoDismiss();
});

// ================= FLASH NOTIFICATION DISMISSAL =================
function showToast(message, type = 'info') {
    const container = document.getElementById('flash-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `flash-toast flash-${type} animate-slide-in`;
    
    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'danger') iconName = 'alert-octagon';
    if (type === 'warning') iconName = 'alert-triangle';

    toast.innerHTML = `
        <div class="flash-icon"><i data-lucide="${iconName}"></i></div>
        <div class="flash-content">${escapeHtml(message)}</div>
        <button class="flash-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
        if (toast.parentElement) toast.remove();
    }, 5000);
}

function initFlashAutoDismiss() {
    const toasts = document.querySelectorAll('.flash-toast');
    toasts.forEach(toast => {
        setTimeout(() => {
            if (toast.parentElement) toast.remove();
        }, 6000);
    });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.innerText = str;
    return div.innerHTML;
}

// ================= DRAG AND DROP & FILE UPLOADS =================
function initDropzone() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');

    if (!dropzone || !fileInput) return;

    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
    }

    dropzone.addEventListener('click', () => {
        fileInput.click();
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            handleFileUpload(files);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFileUpload(fileInput.files);
        }
    });
}

function handleFileUpload(files) {
    const progressContainer = document.getElementById('uploadProgressContainer');
    const progressBar = document.getElementById('globalProgressBar');
    const progressPercent = document.getElementById('uploadProgressPercent');
    const progressTitle = document.getElementById('uploadProgressTitle');
    const statusMessages = document.getElementById('uploadStatusMessages');

    progressContainer.style.display = 'block';
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';
    progressTitle.textContent = `Uploading ${files.length} file(s)...`;
    statusMessages.innerHTML = '';

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/files/upload', true);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            progressBar.style.width = `${percent}%`;
            progressPercent.textContent = `${percent}%`;
        }
    };

    xhr.onload = () => {
        const fileInput = document.getElementById('fileInput');
        if (fileInput) fileInput.value = '';

        if (xhr.status >= 200 && xhr.status < 300) {
            try {
                const res = JSON.parse(xhr.responseText);
                if (res.success) {
                    progressBar.style.width = '100%';
                    progressPercent.textContent = '100%';
                    progressTitle.textContent = 'Upload complete!';
                    
                    showToast(`Successfully uploaded ${res.uploaded.length} file(s).`, 'success');

                    // If partial warnings
                    if (res.errors && res.errors.length > 0) {
                        res.errors.forEach(err => showToast(err, 'warning'));
                    }

                    // Reload dashboard to update table & stats cleanly
                    setTimeout(() => {
                        window.location.reload();
                    }, 800);
                } else {
                    handleUploadError(res.error || 'Upload failed.');
                }
            } catch (err) {
                handleUploadError('Unexpected response from server.');
            }
        } else {
            try {
                const res = JSON.parse(xhr.responseText);
                const msg = res.errors ? res.errors.join('<br>') : (res.error || 'Upload failed.');
                handleUploadError(msg);
            } catch (err) {
                handleUploadError(`Upload error (${xhr.status})`);
            }
        }
    };

    xhr.onerror = () => {
        handleUploadError('Network error while uploading.');
    };

    xhr.send(formData);
}

function handleUploadError(errMsg) {
    const progressTitle = document.getElementById('uploadProgressTitle');
    const progressBar = document.getElementById('globalProgressBar');
    if (progressTitle) progressTitle.textContent = 'Upload failed';
    if (progressBar) {
        progressBar.classList.remove('progress-normal');
        progressBar.classList.add('progress-danger');
    }
    showToast(errMsg, 'danger');
}

// ================= FILE PREVIEW MODAL =================
function openPreviewModal(fileId, filename, mimeType, category) {
    const modal = document.getElementById('previewModal');
    const title = document.getElementById('previewModalTitle');
    const content = document.getElementById('previewContentArea');
    const dlBtn = document.getElementById('previewDownloadBtn');

    title.textContent = `Preview: ${filename}`;
    dlBtn.href = `/api/files/${fileId}/download`;

    content.innerHTML = '<div class="preview-spinner"><i data-lucide="loader" class="spin"></i> Loading preview...</div>';
    modal.style.display = 'flex';
    if (window.lucide) lucide.createIcons();

    const previewUrl = `/api/files/${fileId}/preview`;

    if (category === 'image') {
        content.innerHTML = `<img src="${previewUrl}" alt="${escapeHtml(filename)}" class="preview-img-tag">`;
    } else if (mimeType === 'application/pdf' || filename.toLowerCase().endsWith('.pdf')) {
        content.innerHTML = `<iframe src="${previewUrl}" class="preview-iframe-tag"></iframe>`;
    } else if (category === 'video') {
        content.innerHTML = `<video controls autoplay class="preview-video-tag" src="${previewUrl}"></video>`;
    } else if (category === 'audio') {
        content.innerHTML = `<audio controls autoplay class="preview-audio-tag" src="${previewUrl}"></audio>`;
    } else if (category === 'code' || category === 'document') {
        // Fetch text preview
        fetch(previewUrl)
            .then(res => res.text())
            .then(text => {
                const sanitized = escapeHtml(text.slice(0, 50000));
                content.innerHTML = `<pre class="font-mono text-sm" style="max-height: 480px; overflow: auto; width: 100%; white-space: pre-wrap; padding: 1rem; background: #0b0f19; border-radius: 6px;"><code>${sanitized}</code></pre>`;
            })
            .catch(() => {
                content.innerHTML = `<iframe src="${previewUrl}" class="preview-iframe-tag"></iframe>`;
            });
    } else {
        content.innerHTML = `
            <div class="empty-state">
                <i data-lucide="file-question" style="width: 48px; height: 48px; margin: 0 auto 1rem; color: #94a3b8;"></i>
                <h4>No inline preview available</h4>
                <p class="text-muted text-sm">Download the file to view its full content.</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
    }
}

function closePreviewModal() {
    const modal = document.getElementById('previewModal');
    const content = document.getElementById('previewContentArea');
    if (modal) modal.style.display = 'none';
    if (content) content.innerHTML = '';
}

// ================= SECURE SHARE MODAL =================
function openShareModal(fileId, filename) {
    const modal = document.getElementById('shareModal');
    const filenameEl = document.getElementById('shareModalFilename');
    const fileIdInput = document.getElementById('shareModalFileId');
    const resultArea = document.getElementById('shareResultArea');
    const createForm = document.getElementById('createShareForm');

    filenameEl.textContent = filename;
    fileIdInput.value = fileId;
    resultArea.style.display = 'none';
    createForm.style.display = 'block';

    modal.style.display = 'flex';
}

function closeShareModal() {
    const modal = document.getElementById('shareModal');
    if (modal) modal.style.display = 'none';
}

function handleShareSubmit(e) {
    e.preventDefault();
    const fileId = document.getElementById('shareModalFileId').value;
    const permission = document.querySelector('input[name="sharePermission"]:checked').value;
    const expiresIn = document.getElementById('shareExpiresIn').value;
    const generateBtn = document.getElementById('generateShareBtn');

    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i data-lucide="loader" class="spin"></i> Generating Link...';
    if (window.lucide) lucide.createIcons();

    fetch(`/api/files/${fileId}/share`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            permission: permission,
            expires_in: expiresIn
        })
    })
    .then(res => res.json())
    .then(data => {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i data-lucide="link"></i> Generate Sharing Link';

        if (data.success) {
            const resultArea = document.getElementById('shareResultArea');
            const outputUrl = document.getElementById('shareOutputUrl');
            const notice = document.getElementById('shareResultNotice');

            outputUrl.value = data.share_url;
            notice.textContent = `Permission: ${data.permission.toUpperCase()} | Expires: ${data.expires_at ? new Date(data.expires_at).toLocaleString() : 'Never'}`;
            resultArea.style.display = 'block';
            outputUrl.select();

            showToast('Secure share link created!', 'success');
        } else {
            showToast(data.error || 'Failed to create share link', 'danger');
        }
        if (window.lucide) lucide.createIcons();
    })
    .catch(err => {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i data-lucide="link"></i> Generate Sharing Link';
        showToast('Network error while generating share link', 'danger');
    });
}

function copyShareOutputUrl() {
    const outputUrl = document.getElementById('shareOutputUrl');
    if (!outputUrl) return;

    outputUrl.select();
    outputUrl.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(outputUrl.value).then(() => {
        showToast('Link copied to clipboard!', 'success');
    }).catch(() => {
        document.execCommand('copy');
        showToast('Link copied!', 'success');
    });
}

function copyShareUrl(url) {
    navigator.clipboard.writeText(url).then(() => {
        showToast('Share link copied to clipboard!', 'success');
    }).catch(() => {
        showToast(`Link: ${url}`, 'info');
    });
}

function revokeShareLink(linkId) {
    if (!confirm('Are you sure you want to revoke this share link? Recipients will immediately lose access.')) {
        return;
    }

    fetch(`/api/share/${linkId}/revoke`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast('Share link has been revoked.', 'success');
            const row = document.getElementById(`share-row-${linkId}`);
            if (row) {
                // Update row status
                const statusCell = row.cells[4];
                const actionCell = row.cells[5];
                if (statusCell) statusCell.innerHTML = '<span class="status-pill status-revoked">Revoked</span>';
                if (actionCell) actionCell.innerHTML = '<span class="text-muted text-xs">Access Disabled</span>';
            }
        } else {
            showToast(data.error || 'Failed to revoke link.', 'danger');
        }
    })
    .catch(() => showToast('Error revoking share link', 'danger'));
}

// ================= FILE DELETION =================
let pendingDeleteId = null;

function confirmDelete(fileId, filename) {
    pendingDeleteId = fileId;
    const modal = document.getElementById('deleteModal');
    const filenameEl = document.getElementById('deleteModalFilename');
    filenameEl.textContent = filename;
    modal.style.display = 'flex';
}

function closeDeleteModal() {
    const modal = document.getElementById('deleteModal');
    if (modal) modal.style.display = 'none';
    pendingDeleteId = null;
}

function executeDelete() {
    if (!pendingDeleteId) return;

    const btn = document.getElementById('confirmDeleteBtn');
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Deleting...';
    if (window.lucide) lucide.createIcons();

    fetch(`/api/files/${pendingDeleteId}/delete`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="trash-2"></i> Delete File';
        closeDeleteModal();

        if (data.success) {
            showToast('File deleted successfully.', 'success');
            const row = document.getElementById(`file-row-${pendingDeleteId}`);
            if (row) {
                row.remove();
            }
            // Update stats
            fetchStats();
        } else {
            showToast(data.error || 'Failed to delete file.', 'danger');
        }
    })
    .catch(() => {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="trash-2"></i> Delete File';
        closeDeleteModal();
        showToast('Network error while deleting file', 'danger');
    });
}

function fetchStats() {
    fetch('/api/files/stats')
        .then(res => res.json())
        .then(stats => {
            // Update storage bar if available
            const progressBar = document.querySelector('.stat-storage .progress-bar-fill');
            const meta = document.querySelector('.stat-storage .stat-meta');
            const statValue = document.querySelector('.stat-storage .stat-value');
            if (progressBar) progressBar.style.width = `${stats.storage_percent}%`;
            if (meta) meta.textContent = `${stats.storage_percent}% of storage quota used`;
            if (statValue) statValue.innerHTML = `${stats.storage_used_formatted} <span class="stat-sub">/ ${stats.storage_quota_formatted}</span>`;
            
            const totalFilesValue = document.querySelector('.stat-files .stat-value');
            if (totalFilesValue) totalFilesValue.innerHTML = `${stats.total_files} <span class="stat-sub">files</span>`;
        })
        .catch(() => {});
}

function toggleShareSection() {
    const body = document.getElementById('shareSectionBody');
    const arrow = document.getElementById('shareSectionArrow');
    if (!body) return;

    if (body.style.display === 'none') {
        body.style.display = 'block';
        if (arrow) arrow.style.transform = 'rotate(0deg)';
    } else {
        body.style.display = 'none';
        if (arrow) arrow.style.transform = 'rotate(-90deg)';
    }
}
