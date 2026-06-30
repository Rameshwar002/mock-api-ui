/* ═══════════════════════════════════════════
   upload.js — File Upload & Controls
═══════════════════════════════════════════ */

let pumlContent = '';
let fileTitle   = 'testcases';

/* ── Wire the upload drop zone ── */
function initUpload() {
  const dropZone  = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const genBtn    = document.getElementById('btn-generate');

  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) loadFile(file);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) loadFile(fileInput.files[0]);
  });

  if (genBtn) genBtn.addEventListener('click', () => {
    if (typeof runGenerate === 'function') runGenerate();
  });

  // Limit slider sync
  const limitInput  = document.getElementById('tc-limit');
  const limitSlider = document.getElementById('tc-slider');
  if (limitInput && limitSlider) {
    limitInput.addEventListener('input', () => {
      limitSlider.value = limitInput.value;
      if (typeof knowledge !== 'undefined') knowledge.mincount = parseInt(limitInput.value) || 8;
    });
    limitSlider.addEventListener('input', () => {
      limitInput.value  = limitSlider.value;
      if (typeof knowledge !== 'undefined') knowledge.mincount = parseInt(limitSlider.value) || 8;
    });
  }
}

/* ── Load & validate file ── */
function loadFile(file) {
  // Validate extension
  const allowed = ['.puml', '.plantuml', '.txt', '.md'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showUploadErr(`Unsupported file type "${ext}". Please upload a .puml or .txt file.`);
    return;
  }
  // Validate size (max 1MB)
  if (file.size > 1024 * 1024) {
    showUploadErr('File is too large (max 1 MB).');
    return;
  }

  const r = new FileReader();
  r.onload = e => {
    const content = e.target.result;

    // Basic content validation
    if (!content.trim()) {
      showUploadErr('The file appears to be empty.');
      return;
    }
    if (!content.includes('@startuml') && !content.includes('title') && !content.includes('->')) {
      showUploadErr('File does not appear to be a valid PlantUML diagram. Make sure it contains @startuml or sequence arrows.');
      return;
    }

    pumlContent = content;
    fileTitle   = file.name.replace(/\.\w+$/, '');

    // Update UI
    const tagRow  = document.getElementById('file-tag-row');
    const tagName = document.getElementById('file-tag-name');
    if (tagRow)  tagRow.classList.add('show');
    if (tagName) tagName.textContent = file.name;

    const errBanner = document.getElementById('tc-err');
    if (errBanner) errBanner.classList.remove('show');

    const genBtn = document.getElementById('btn-generate');
    if (genBtn) genBtn.disabled = false;
  };
  r.onerror = () => showUploadErr('Could not read file. Please try again.');
  r.readAsText(file);
}

/* ── Show upload error ── */
function showUploadErr(msg) {
  const el = document.getElementById('tc-err');
  if (el) { el.innerHTML = `<strong>Upload error</strong><br>${msg}`; el.classList.add('show'); }
}

/* ── Reset upload state ── */
function resetUploadState() {
  pumlContent = '';
  fileTitle   = 'testcases';
  const tagRow  = document.getElementById('file-tag-row');
  const tagName = document.getElementById('file-tag-name');
  const genBtn  = document.getElementById('btn-generate');
  const errEl   = document.getElementById('tc-err');
  if (tagRow)  tagRow.classList.remove('show');
  if (tagName) tagName.textContent = '';
  if (genBtn)  genBtn.disabled = true;
  if (errEl)   errEl.classList.remove('show');
  const fi = document.getElementById('file-input');
  if (fi) fi.value = '';
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', initUpload);
