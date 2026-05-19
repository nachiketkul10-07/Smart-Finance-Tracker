/* ══════════════════════════════════════════════════════════════════════════
   Smart Finance Tracker — Mobile PWA App Logic
   Connects to FastAPI backend at /api/
   ══════════════════════════════════════════════════════════════════════════ */

const API = window.location.hostname === 'localhost'
  ? 'http://127.0.0.1:8000' : window.location.origin;

// ── State ───────────────────────────────────────────────────────────────
let token  = localStorage.getItem('ft_token') || '';
let user   = JSON.parse(localStorage.getItem('ft_user') || 'null');
let currentPage = 'dashboard';

const EXPENSE_CATS = [
  'Food & Dining','Transport','Shopping','Entertainment','Bills & Utilities',
  'Health','Education','Rent','Travel','Groceries','Personal Care',
  'Gifts & Donations','Subscriptions','Other'
];
const INCOME_CATS = [
  'Salary','Freelance','Business','Investments','Refund','Gift','Other'
];
const PAY_MODES = ['Cash','UPI','Debit Card','Credit Card','Net Banking','Auto-Debit'];
const CAT_ICONS = {
  'Food & Dining':'🍕','Transport':'🚗','Shopping':'🛍️','Entertainment':'🎬',
  'Bills & Utilities':'💡','Health':'💊','Education':'📚','Rent':'🏠',
  'Travel':'✈️','Groceries':'🥦','Personal Care':'💇','Gifts & Donations':'🎁',
  'Subscriptions':'📺','Salary':'💼','Freelance':'💻','Business':'📈',
  'Investments':'📊','Refund':'↩️','Gift':'🎁','Other':'📌'
};

// ── API Helpers ─────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  try {
    const res = await fetch(`${API}${path}`, { ...opts, headers });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
  } catch (e) {
    if (e.message.includes('Failed to fetch')) throw new Error('Cannot reach server');
    throw e;
  }
}

function toast(msg) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function fmt(n) {
  return '₹' + Number(n).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtDate(d) {
  const dt = new Date(d);
  return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function today() {
  return new Date().toISOString().split('T')[0];
}

// ── Auth ────────────────────────────────────────────────────────────────
function initAuth() {
  // Tabs
  document.querySelectorAll('#auth-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#auth-tabs .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const isLogin = tab.dataset.tab === 'login';
      document.getElementById('login-form').style.display = isLogin ? 'block' : 'none';
      document.getElementById('register-form').style.display = isLogin ? 'none' : 'block';
    });
  });

  // Login
  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const err = document.getElementById('login-error');
    btn.textContent = 'Logging in...'; btn.disabled = true; err.textContent = '';
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          username: document.getElementById('login-user').value.trim(),
          password: document.getElementById('login-pass').value
        })
      });
      token = data.access_token;
      user = data.user;
      localStorage.setItem('ft_token', token);
      localStorage.setItem('ft_user', JSON.stringify(user));
      showApp();
    } catch (e) {
      err.textContent = e.message;
    }
    btn.textContent = 'Login'; btn.disabled = false;
  });

  // Register
  document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('reg-btn');
    const err = document.getElementById('reg-error');
    btn.textContent = 'Creating...'; btn.disabled = true; err.textContent = '';
    try {
      await api('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          full_name: document.getElementById('reg-name').value.trim(),
          username: document.getElementById('reg-user').value.trim(),
          email: document.getElementById('reg-email').value.trim(),
          password: document.getElementById('reg-pass').value
        })
      });
      toast('Account created! Logging in...');
      // Auto-login
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          username: document.getElementById('reg-user').value.trim(),
          password: document.getElementById('reg-pass').value
        })
      });
      token = data.access_token;
      user = data.user;
      localStorage.setItem('ft_token', token);
      localStorage.setItem('ft_user', JSON.stringify(user));
      showApp();
    } catch (e) {
      err.textContent = e.message;
    }
    btn.textContent = 'Create Account'; btn.disabled = false;
  });

  // Logout
  document.getElementById('logout-btn').addEventListener('click', () => {
    token = ''; user = null;
    localStorage.removeItem('ft_token');
    localStorage.removeItem('ft_user');
    document.getElementById('app-screen').style.display = 'none';
    document.getElementById('auth-screen').style.display = 'flex';
  });
}

// ── Navigation ──────────────────────────────────────────────────────────
function initNav() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      if (!btn.classList.contains('add-btn')) btn.classList.add('active');
      navigate(btn.dataset.page);
    });
  });
}

function navigate(page) {
  currentPage = page;
  const container = document.getElementById('page-container');
  container.innerHTML = '<div class="spinner"></div>';
  container.scrollTop = 0;

  switch (page) {
    case 'dashboard':   renderDashboard(container); break;
    case 'transactions': renderTransactions(container); break;
    case 'add':         renderAddForm(container); break;
    case 'analytics':   renderAnalytics(container); break;
    case 'settings':    renderSettings(container); break;
  }
}

// ── Dashboard ───────────────────────────────────────────────────────────
async function renderDashboard(el) {
  try {
    const [summary, txns] = await Promise.all([
      api('/api/analytics/summary'),
      api('/api/transactions/')
    ]);

    const balance = (summary.total_income || 0) - (summary.total_expense || 0);
    const recent = (txns.transactions || txns).slice(0, 8);

    el.innerHTML = `
      <div class="balance-card">
        <div class="balance-label">Total Balance</div>
        <div class="balance-amount">${fmt(balance)}</div>
        <div class="balance-row">
          <div class="balance-box income">
            <div class="balance-box-label">Income</div>
            <div class="balance-box-amount">↑ ${fmt(summary.total_income || 0)}</div>
          </div>
          <div class="balance-box expense">
            <div class="balance-box-label">Expenses</div>
            <div class="balance-box-amount">↓ ${fmt(summary.total_expense || 0)}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Recent Transactions</div>
        ${recent.length ? recent.map(t => txnItem(t)).join('') :
          '<div class="empty-state"><div class="empty-icon">📭</div>' +
          '<div class="empty-title">No transactions yet</div>' +
          '<div class="empty-sub">Tap + to add your first one</div></div>'}
      </div>
    `;
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div>
      <div class="empty-title">Connection Error</div>
      <div class="empty-sub">${e.message}<br>Make sure the API server is running</div></div>`;
  }
}

function txnItem(t) {
  const icon = CAT_ICONS[t.category] || '📌';
  const cls = t.type === 'income' ? 'income' : 'expense';
  const sign = t.type === 'income' ? '+' : '-';
  return `
    <div class="txn-item">
      <div class="txn-icon ${cls}">${icon}</div>
      <div class="txn-info">
        <div class="txn-cat">${t.category}</div>
        <div class="txn-note">${t.note || t.payment_mode || ''}</div>
      </div>
      <div class="txn-right">
        <div class="txn-amount ${cls}">${sign}${fmt(t.amount)}</div>
        <div class="txn-date">${fmtDate(t.trans_date)}</div>
      </div>
    </div>`;
}

// ── Transactions ────────────────────────────────────────────────────────
async function renderTransactions(el) {
  try {
    const txns = await api('/api/transactions/');
    const list = txns.transactions || txns;

    el.innerHTML = `
      <div class="card">
        <div class="card-title">All Transactions (${list.length})</div>
        ${list.length ? list.map(t => txnItem(t)).join('') :
          '<div class="empty-state"><div class="empty-icon">📭</div>' +
          '<div class="empty-title">No transactions</div>' +
          '<div class="empty-sub">Add income or expenses to get started</div></div>'}
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div>
      <div class="empty-title">${e.message}</div></div>`;
  }
}

// ── Add Transaction ─────────────────────────────────────────────────────
function renderAddForm(el) {
  let txnType = 'expense';

  el.innerHTML = `
    <div class="card">
      <div class="card-title">New Transaction</div>

      <div class="type-toggle">
        <button class="type-btn expense active" id="type-expense">💸 Expense</button>
        <button class="type-btn income" id="type-income">💰 Income</button>
      </div>

      <form id="add-form">
        <div class="input-group">
          <label>Amount (₹)</label>
          <input type="number" id="add-amount" placeholder="0" min="1" step="0.01" required inputmode="decimal">
        </div>

        <div class="input-group">
          <label>Category</label>
          <select id="add-category">
            ${EXPENSE_CATS.map(c => `<option value="${c}">${CAT_ICONS[c]||''} ${c}</option>`).join('')}
          </select>
        </div>

        <div class="form-row">
          <div class="input-group">
            <label>Date</label>
            <input type="date" id="add-date" value="${today()}" required>
          </div>
          <div class="input-group">
            <label>Payment Mode</label>
            <select id="add-mode">
              ${PAY_MODES.map(m => `<option value="${m}">${m}</option>`).join('')}
            </select>
          </div>
        </div>

        <div class="input-group">
          <label>Note (optional)</label>
          <input type="text" id="add-note" placeholder="What was this for?" maxlength="100">
        </div>

        <button type="submit" class="btn-primary" id="add-btn">Add Transaction</button>
      </form>
    </div>`;

  // Type toggle
  const updateCats = () => {
    const cats = txnType === 'expense' ? EXPENSE_CATS : INCOME_CATS;
    document.getElementById('add-category').innerHTML =
      cats.map(c => `<option value="${c}">${CAT_ICONS[c]||''} ${c}</option>`).join('');
  };

  document.getElementById('type-expense').addEventListener('click', () => {
    txnType = 'expense';
    document.getElementById('type-expense').classList.add('active');
    document.getElementById('type-income').classList.remove('active');
    updateCats();
  });
  document.getElementById('type-income').addEventListener('click', () => {
    txnType = 'income';
    document.getElementById('type-income').classList.add('active');
    document.getElementById('type-expense').classList.remove('active');
    updateCats();
  });

  // Submit
  document.getElementById('add-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('add-btn');
    btn.textContent = 'Saving...'; btn.disabled = true;
    try {
      await api('/api/transactions/', {
        method: 'POST',
        body: JSON.stringify({
          type: txnType,
          amount: parseFloat(document.getElementById('add-amount').value),
          category: document.getElementById('add-category').value,
          trans_date: document.getElementById('add-date').value,
          payment_mode: document.getElementById('add-mode').value,
          note: document.getElementById('add-note').value || ''
        })
      });
      toast('✅ Transaction added!');
      // Navigate to dashboard
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      document.querySelector('[data-page="dashboard"]').classList.add('active');
      navigate('dashboard');
    } catch (e) {
      toast('❌ ' + e.message);
    }
    btn.textContent = 'Add Transaction'; btn.disabled = false;
  });
}

// ── Analytics ───────────────────────────────────────────────────────────
async function renderAnalytics(el) {
  try {
    const summary = await api('/api/analytics/summary');
    const txns = await api('/api/transactions/');
    const list = txns.transactions || txns;

    // Category breakdown
    const catMap = {};
    list.filter(t => t.type === 'expense').forEach(t => {
      catMap[t.category] = (catMap[t.category] || 0) + t.amount;
    });
    const catEntries = Object.entries(catMap).sort((a, b) => b[1] - a[1]);
    const maxCat = catEntries.length ? catEntries[0][1] : 1;

    const expenses = list.filter(t => t.type === 'expense');
    const avgExpense = expenses.length ? expenses.reduce((s,t) => s+t.amount, 0) / expenses.length : 0;

    el.innerHTML = `
      <div class="stat-grid">
        <div class="stat-box">
          <div class="stat-value" style="color:var(--green)">${fmt(summary.total_income || 0)}</div>
          <div class="stat-label">Total Income</div>
        </div>
        <div class="stat-box">
          <div class="stat-value" style="color:var(--red)">${fmt(summary.total_expense || 0)}</div>
          <div class="stat-label">Total Expenses</div>
        </div>
        <div class="stat-box">
          <div class="stat-value" style="color:var(--primary)">${list.length}</div>
          <div class="stat-label">Transactions</div>
        </div>
        <div class="stat-box">
          <div class="stat-value" style="color:var(--orange)">${fmt(avgExpense)}</div>
          <div class="stat-label">Avg Expense</div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Top Categories</div>
        <div class="bar-chart">
          ${catEntries.length ? catEntries.slice(0, 6).map(([cat, amt]) => `
            <div class="bar-row">
              <div class="bar-label">${CAT_ICONS[cat]||''} ${cat}</div>
              <div class="bar-track">
                <div class="bar-fill" style="width:${(amt/maxCat*100).toFixed(1)}%"></div>
              </div>
              <div class="bar-value">${fmt(amt)}</div>
            </div>
          `).join('') :
          '<div class="empty-state"><div class="empty-sub">No expense data yet</div></div>'}
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div>
      <div class="empty-title">${e.message}</div></div>`;
  }
}

// ── Settings ────────────────────────────────────────────────────────────
function renderSettings(el) {
  el.innerHTML = `
    <div class="card">
      <div class="card-title">Account</div>
      <div class="settings-item">
        <div class="settings-left">
          <span class="settings-icon">👤</span>
          <div>
            <div class="settings-label">${user?.full_name || user?.username || 'User'}</div>
            <div class="settings-desc">@${user?.username || ''}</div>
          </div>
        </div>
      </div>
      <div class="settings-item">
        <div class="settings-left">
          <span class="settings-icon">📧</span>
          <div>
            <div class="settings-label">Email</div>
            <div class="settings-desc">${user?.email || 'Not set'}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Import Sources</div>
      <div class="settings-item">
        <div class="settings-left">
          <span class="settings-icon">🏦</span>
          <div>
            <div class="settings-label">Bank Statement</div>
            <div class="settings-desc">CSV, Excel, PDF — 14 banks</div>
          </div>
        </div>
        <div class="settings-right">✅</div>
      </div>
      <div class="settings-item">
        <div class="settings-left">
          <span class="settings-icon">📸</span>
          <div>
            <div class="settings-label">UPI Screenshot OCR</div>
            <div class="settings-desc">GPay, PhonePe, Paytm + more</div>
          </div>
        </div>
        <div class="settings-right">✅</div>
      </div>
      <div class="settings-item">
        <div class="settings-left">
          <span class="settings-icon">📧</span>
          <div>
            <div class="settings-label">Gmail Email Sync</div>
            <div class="settings-desc">Auto-import bank alerts</div>
          </div>
        </div>
        <div class="settings-right">✅</div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">About</div>
      <div class="settings-item">
        <div class="settings-left">
          <span class="settings-icon">🚀</span>
          <div>
            <div class="settings-label">Smart Finance Tracker v2.0</div>
            <div class="settings-desc">Built with FastAPI + Streamlit + PWA</div>
          </div>
        </div>
      </div>
    </div>

    <button class="btn-primary" style="background:linear-gradient(135deg,#e74c3c,#c0392b);margin-top:0.5rem;"
      id="settings-logout">Logout</button>
  `;

  document.getElementById('settings-logout').addEventListener('click', () => {
    document.getElementById('logout-btn').click();
  });
}

// ── Boot ────────────────────────────────────────────────────────────────
function showApp() {
  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'block';
  document.getElementById('user-badge').textContent = '@' + (user?.username || '');
  navigate('dashboard');
}

function init() {
  // Hide splash after 1.2s
  setTimeout(() => {
    document.getElementById('splash').style.display = 'none';
    if (token && user) {
      showApp();
    } else {
      document.getElementById('auth-screen').style.display = 'flex';
    }
  }, 1200);

  initAuth();
  initNav();

  // Register service worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

document.addEventListener('DOMContentLoaded', init);
