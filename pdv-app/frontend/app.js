// Minimal router + state
const $ = (sel, ctx=document) => ctx.querySelector(sel);
const $$ = (sel, ctx=document) => Array.from(ctx.querySelectorAll(sel));

const state = {
  items: [],
  subtotal: 0,
  total: 0
};

const currency = (n) => (n||0).toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2});

function recalc() {
  state.subtotal = state.items.reduce((s, it) => s + it.qty * it.price, 0);
  const frete = parseFloat($('#frete').value || 0);
  let descV = parseFloat($('#descontoValor').value || 0);
  let descP = parseFloat($('#descontoPct').value || 0);
  const desc = descV + (state.subtotal * (descP/100));
  state.total = Math.max(0, state.subtotal + frete - desc);
  $('#subtotal').textContent = currency(state.subtotal);
  $('#total').textContent = currency(state.total);
  const recebido = parseFloat($('#recebido').value || 0);
  $('#troco').textContent = currency(Math.max(0, recebido - state.total));
}

function renderItems() {
  const tbody = $('#itensTable tbody');
  tbody.innerHTML = '';
  state.items.forEach((it, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${it.name}</td>
      <td>${it.variant ?? '-'}</td>
      <td><input type="number" min="1" step="1" value="${it.qty}" data-idx="${idx}" class="qty-input"></td>
      <td>${currency(it.price)}</td>
      <td>${currency(it.qty * it.price)}</td>
      <td><button class="btn" data-remove="${idx}" aria-label="Remover ${it.name}">✕</button></td>
    `;
    tbody.appendChild(tr);
  });
  recalc();
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.altKey && (e.key === 'd' || e.key === 'D')) {
    e.preventDefault();
    toggleTheme();
  }
  if (e.ctrlKey && e.key === 'Backspace') {
    e.preventDefault();
    state.items = [];
    renderItems();
  }
});

// Tabs
$$('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected','false'); });
    tab.classList.add('active'); tab.setAttribute('aria-selected','true');
    const id = tab.dataset.tab;
    $$('#tab-pdv, #tab-historico').forEach(sec => sec.classList.add('is-hidden'));
    $('#tab-' + id).classList.remove('is-hidden');
    $('#tab-' + id).setAttribute('aria-hidden', 'false');
  });
});

// Theme
const root = document.documentElement;
function setTheme(mode) {
  root.setAttribute('data-theme', mode);
  $('#themeLabel').textContent = mode === 'dark' ? 'Dark' : 'Light';
  $('#themeToggle').setAttribute('aria-pressed', mode === 'dark' ? 'true' : 'false');
  localStorage.setItem('theme', mode);
}
function toggleTheme() {
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  setTheme(next);
}
$('#themeToggle').addEventListener('click', toggleTheme);
setTheme(localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

// Load some clients (demo)
async function loadClients() {
  try {
    const res = await fetch('/api/clients?limit=50');
    const data = await res.json();
    const dl = $('#clientes');
    dl.innerHTML = '';
    (data.items || []).forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      dl.appendChild(opt);
    });
  } catch (e) { /* ignore on local file */ }
}
loadClients();

// Add item
$('#scanForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const sku = $('#skuInput').value.trim();
  const qty = parseInt($('#qtyInput').value || '1', 10);
  const priceManual = parseFloat($('#priceInput').value || 'NaN');

  let product = null;
  if (sku) {
    try {
      const res = await fetch('/api/products/find?query=' + encodeURIComponent(sku));
      if (res.ok) product = await res.json();
    } catch (err) { /* offline demo */ }
  }
  if (!product) {
    product = { sku, name: sku || 'Item Manual', price: isFinite(priceManual) ? priceManual : 0 };
  }
  const price = isFinite(priceManual) ? priceManual : (product.price || 0);

  state.items.push({ sku: product.sku, name: product.name, variant: product.variant, qty: qty, price: price });
  $('#skuInput').value=''; $('#priceInput').value='';
  renderItems();
});

$('#itensTable').addEventListener('input', (e) => {
  const idx = e.target.dataset.idx;
  if (idx !== undefined) {
    state.items[idx].qty = Math.max(1, parseInt(e.target.value || '1', 10));
    renderItems();
  }
});
$('#itensTable').addEventListener('click', (e) => {
  const idx = e.target.dataset.remove;
  if (idx !== undefined) {
    state.items.splice(parseInt(idx,10), 1);
    renderItems();
  }
});

// Discounts / totals
$('#aplicarDesconto').addEventListener('click', (e) => { e.preventDefault(); recalc(); });
['descontoValor','descontoPct','frete','recebido'].forEach(id => {
  $('#' + id).addEventListener('input', recalc);
});

// Close sale
$('#fecharVenda').addEventListener('click', async (e) => {
  e.preventDefault();
  if (state.items.length === 0) return alert('Adicione ao menos 1 item.');
  const payload = {
    client_name: $('#clienteInput').value || null,
    payment: $('#pagamento').value,
    installments: parseInt($('#parcelas').value || '1', 10),
    discount_value: parseFloat($('#descontoValor').value || 0),
    discount_pct: parseFloat($('#descontoPct').value || 0),
    freight: parseFloat($('#frete').value || 0),
    received: parseFloat($('#recebido').value || 0),
    subtotal: state.subtotal,
    total: state.total,
    items: state.items
  };
  try {
    const res = await fetch('/api/sales', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const data = await res.json();
    alert('Venda #' + data.id + ' registrada!');
    state.items = [];
    renderItems();
    loadHistory();
  } catch(err) {
    console.warn(err);
    alert('Sem backend? Rode o FastAPI para salvar as vendas.');
  }
});

// History
async function loadHistory() {
  try {
    const res = await fetch('/api/sales?limit=20');
    const data = await res.json();
    const list = $('#historyList');
    list.innerHTML = '';
    (data.items || []).forEach(sale => {
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = `
        <strong>Venda #${sale.id}</strong> — ${new Date(sale.created_at).toLocaleString('pt-BR')}
        <div class="muted small">Cliente: ${sale.client_name || '-'}</div>
        <div>Total: R$ ${currency(sale.total)} • Itens: ${sale.items.length}</div>
      `;
      list.appendChild(card);
    });
  } catch(e) {/* ignore */}
}
loadHistory();
