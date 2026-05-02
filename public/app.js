let currentOS = 'mac';
let db = null;

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

async function loadDB() {
  if (db) return db;
  const res = await fetch('/data/operations.json');
  db = await res.json();
  return db;
}

function tokenize(query) {
  const stopWords = ['したい', 'たい', 'する', 'して', 'した', 'を', 'は', 'が', 'に', 'で', 'の', 'と', 'から', 'まで', 'よ', 'ね', 'か', 'も', 'ます', 'ない', 'です'];
  let text = query;
  for (const sw of stopWords) text = text.replaceAll(sw, ' ');
  return text.split(/[\s、。　！？!?]+/).map(t => t.trim()).filter(t => t.length >= 2);
}

function scoreOp(op, tokens, raw) {
  let score = 0;
  const rawLower = raw.toLowerCase();
  const nameLower = op.name.toLowerCase();

  if (nameLower === rawLower) score += 100;
  for (const t of tokens) {
    if (nameLower.includes(t.toLowerCase())) score += 30;
  }
  for (const kw of op.keywords) {
    const kwLower = kw.toLowerCase();
    if (kwLower === rawLower) score += 50;
    if (tokens.some(t => t.toLowerCase() === kwLower)) score += 50;
    for (const t of tokens) {
      const tl = t.toLowerCase();
      if (kwLower.includes(tl) || tl.includes(kwLower)) score += 20;
    }
  }
  if (op.category) {
    for (const t of tokens) {
      if (op.category.includes(t)) score += 10;
    }
  }
  const bodyText = [...(op.steps || []), op.tips || '', op.menu_path || ''].join(' ').toLowerCase();
  for (const t of tokens) {
    if (bodyText.includes(t.toLowerCase())) score += 5;
  }
  return score;
}

function search(query) {
  if (!db) return null;
  const tokens = tokenize(query);
  if (tokens.length === 0) return null;

  const results = db.operations
    .map(op => ({ op, score: scoreOp(op, tokens, query) }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(({ op }) => op);

  if (results.length === 0) return null;
  return {
    summary: `「${query}」に関連する操作が ${results.length} 件見つかりました`,
    operations: results,
  };
}

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
    await loadDB();
    const result = search(query);
    if (!result) {
      showError('該当する操作が見つかりませんでした。別のキーワードでお試しください。');
    } else {
      renderResult(result);
    }
  } catch (err) {
    showError('データの読み込みに失敗しました: ' + err.message);
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

  const header = document.createElement('div');
  header.className = 'op-card-header';
  header.innerHTML = `<span class="op-number">${num}</span><span class="op-name">${esc(op.name)}</span>`;
  card.appendChild(header);

  const body = document.createElement('div');
  body.className = 'op-card-body';

  if (op.shortcut_mac || op.shortcut_win) {
    const row = document.createElement('div');
    row.className = 'info-row';
    const display = document.createElement('div');
    display.className = 'shortcut-display';
    display.dataset.macShortcut = op.shortcut_mac || '';
    display.dataset.winShortcut = op.shortcut_win || '';
    display.innerHTML = renderShortcut(currentOS === 'mac' ? op.shortcut_mac : op.shortcut_win);
    row.innerHTML = `<span class="info-label">ショートカット</span>`;
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
  return `<div class="menu-path">${steps.map((s, i) =>
    `<span class="menu-step">${esc(s)}</span>${i < steps.length - 1 ? '<span class="menu-arrow">▶</span>' : ''}`
  ).join('')}</div>`;
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
