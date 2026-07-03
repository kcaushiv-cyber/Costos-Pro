/* ============================================================
   COSTOS PRO — Upload de imágenes reutilizable
   Uso: uploadImg(inputId, previewId, thumbId, hiddenId)
   ============================================================ */

async function uploadImg(inputId, previewId, thumbId, hiddenId) {
  const input = document.getElementById(inputId);
  const file  = input?.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('image', file);

  showToast('Subiendo imagen...', 'info');

  try {
    const res  = await fetch('/ai/upload/image', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.success) {
      document.getElementById(hiddenId).value   = data.path;
      document.getElementById(thumbId).src       = data.path;
      document.getElementById(previewId).style.display = 'block';
      showToast('Imagen subida', 'success');
    } else {
      showToast(data.error || 'Error al subir imagen', 'error');
    }
  } catch (e) {
    showToast('Error de conexión', 'error');
  }
}

// Drag & drop en elementos con data-upload-target
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-upload-target]').forEach(zone => {
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--primary)'; });
    zone.addEventListener('dragleave', () => { zone.style.borderColor = 'var(--border)'; });
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.style.borderColor = 'var(--border)';
      const target = zone.dataset.uploadTarget;
      const cfg    = JSON.parse(target);
      const file   = e.dataTransfer.files[0];
      if (!file) return;
      const input  = document.getElementById(cfg.input);
      if (input) {
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        uploadImg(cfg.input, cfg.preview, cfg.thumb, cfg.hidden);
      }
    });
  });
});
