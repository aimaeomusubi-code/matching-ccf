let currentOS = 'mac';

const form = document.getElementById('search-form');
const queryInput = document.getElementById('query-input');
const submitBtn = document.getElementById('submit-btn');
const resultSection = document.getElementById('result-section');
const loading = document.getElementById('loading');
const errorMsg = document.getElementById('error-msg');
const resultContent = document.getElementById('result-content');
const resultSummary = document.getElementById('result-summary');
const operationsGrid = document.getElementById('operations-grid');
const examplesSection = document.getElementById('examples-section');

document.querySelectorAll('.os-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.os-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentOS = btn.dataset.os;
    updateShortcutDisplays();
  });
});

document.querySelectorAll('.example-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    queryInput.value = chip.textContent;
    queryInput.focus();
    form.dispatchEvent(new Event('submit'));
  });
});

queryInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    form.dispatchEvent(new Event('submit'));
  }
});

form.addEventListener('submit', async e => {
  e.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;

  setLoading(true);
  examplesSection.classList.add('hidden');

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'エラーが発生しました');
    renderResult(data);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
});

function setLoading(on) {
  submitBtn.disabled = on;
  resultSection.classList.remove('hidden');
  loading.classList.toggle('hidden', !on);
  errorMsg.classList.add('hidden');
  resultContent.classList.add('hidden');
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.classList.remove('hidden');
}

function renderResult(data) {
  resultSummary.textContent = data.summary || '';
  operationsGrid.innerHTML = '';

  (data.operations || []).forEach((op, i) => {
    operationsGrid.appendChild(buildCard(op, i + 1));
  });

  resultContent.classList.remove('hidden');
}

function buildCard(op, num) {
  const card = document.createElement('div');
  card.className = 'op-card';
  card.dataset.mac = op.shortcut_mac || '';
  card.dataset.win = op.shortcut_win || '';

  const header = document.createElement('div');
  header.className = 'op-card-header';
  header.innerHTML = `<span class="op-number">${num}</span><span class="op-name">${esc(op.name)}</span>`;
  card.appendChild(header);

  const body = document.createElement('div');
  body.className = 'op-card-body';

  const shortcutMac = op.shortcut_mac;
  const shortcutWin = op.shortcut_win;
  if (shortcutMac || shortcutWin) {
    const row = document.createElement('div');
    row.className = 'info-row';
    row.innerHTML = `<span class="info-label">ショートカット</span>`;
    const display = document.createElement('div');
    display.className = 'shortcut-display';
    display.dataset.macShortcut = shortcutMac || '';
    display.dataset.winShortcut = shortcutWin || '';
    display.innerHTML = renderShortcut(currentOS === 'mac' ? shortcutMac : shortcutWin);
    row.appendChild(display);
    body.appendChild(row);
  }

  if (op.menu_path) {
    const row = document.createElement('div');
    row.className = 'info-row';
    row.innerHTML = `<span class="info-label">メニューの場所</span>${renderMenuPath(op.menu_path)}`;
    body.appendChild(row);
  }

  if (op.panel) {
    const row = document.createElement('div');
    row.className = 'info-row';
    row.innerHTML = `<span class="info-label">パネル</span><span class="panel-badge">${esc(op.panel)}</span>`;
    body.appendChild(row);
  }

  if (op.steps && op.steps.length) {
    const row = document.createElement('div');
    row.className = 'info-row';
    const list = op.steps.map((s, idx) =>
      `<li class="step-item"><span class="step-num">${idx + 1}</span><span>${esc(s)}</span></li>`
    ).join('');
    row.innerHTML = `<span class="info-label">操作手順</span><ol class="steps-list">${list}</ol>`;
    body.appendChild(row);
  }

  if (op.tips) {
    const row = document.createElement('div');
    row.className = 'info-row';
    row.innerHTML = `<span class="info-label">ヒント</span><p class="tips-text"><span class="tips-icon">&#9679;</span>${esc(op.tips)}</p>`;
    body.appendChild(row);
  }

  card.appendChild(body);
  return card;
}

function renderShortcut(shortcut) {
  if (!shortcut) return '<span style="color:var(--text-muted)">なし</span>';
  const parts = shortcut.split(/\s*\+\s*/);
  return `<span class="key-combo">${parts.map((p, i) =>
    `<kbd>${esc(p)}</kbd>${i < parts.length - 1 ? '<span class="key-sep">+</span>' : ''}`
  ).join('')}</span>`;
}

function renderMenuPath(path) {
  const steps = path.split(/\s*[→>]\s*/);
  const html = steps.map((s, i) =>
    `<span class="menu-step">${esc(s)}</span>${i < steps.length - 1 ? '<span class="menu-arrow">▶</span>' : ''}`
  ).join('');
  return `<div class="menu-path">${html}</div>`;
}

function updateShortcutDisplays() {
  document.querySelectorAll('.shortcut-display').forEach(el => {
    const shortcut = currentOS === 'mac' ? el.dataset.macShortcut : el.dataset.winShortcut;
    el.innerHTML = renderShortcut(shortcut || null);
  });
}

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
