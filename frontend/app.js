// ===== Helpers =====
const $  = (s, c=document) => c.querySelector(s);
const $$ = (s, c=document) => Array.from(c.querySelectorAll(s));
function on(el, ev, fn){ if (el) el.addEventListener(ev, fn); }
const currency = n => (n||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
function fmtDate(d){ const x=new Date(d); const m=String(x.getMonth()+1).padStart(2,'0'); const dd=String(x.getDate()).padStart(2,'0'); return `${x.getFullYear()}-${m}-${dd}`; }

// ===== Tema (Dark/Light) =====
const root = document.documentElement;
function setTheme(mode){
  root.setAttribute("data-theme", mode);
  const lbl = $("#themeLabel"); if (lbl) lbl.textContent = mode === "dark" ? "Dark" : "Light";
  const tg  = $("#themeToggle"); if (tg) tg.setAttribute("aria-pressed", mode === "dark" ? "true" : "false");
  localStorage.setItem("theme", mode);
}
function toggleTheme(){ setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark"); }
on($("#themeToggle"), "click", toggleTheme);
setTheme(localStorage.getItem("theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));

// ===== Token / API =====
const API = ""; // mesma origem
function getToken(){ return localStorage.getItem("pdv_token"); }
function setToken(t){ if (t) localStorage.setItem("pdv_token", t); else localStorage.removeItem("pdv_token"); }

// Fetch JSON (padrão)
async function apiFetch(path, opts = {}){
  const t = getToken();
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(opts.headers || {}),
    ...(t ? { Authorization: `Bearer ${t}` } : {}),
  };
  let res;
  try{
    res = await fetch(`${API}${path}`, { ...opts, headers });
  }catch(e){
    if (!opts.returnResponse) {
      const err = new Error("Servidor indisponível.");
      err.status = 0;
      throw err;
    }
    return { ok:false, status:0, text:async()=> "Servidor indisponível" };
  }
  if (opts.returnResponse) return res;

  if (!res.ok){
    const msg = await res.text().catch(()=> "");
    const err = new Error(msg || res.statusText);
    err.status = res.status;
    throw err;
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : null;
}

// Upload (multipart) — usado para imagem de produto
async function uploadFile(path, file){
  const fd = new FormData();
  fd.append("file", file);
  const headers = {};
  const t = getToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(`${API}${path}`, { method: "POST", headers, body: fd });
  if (!res.ok){
    const msg = await res.text().catch(()=> "");
    throw new Error(msg || "Falha no upload");
  }
  return res.json(); // deve retornar { url: "/uploads/products/xxx.ext" }
}

// Mantém tratamento 401 centralizado
async function api(path, options = {}){
  const res = await apiFetch(path, { ...options, returnResponse: true });
  if (res.status === 401){
    setLoggedIn(null, null);
    throw new Error("Sessão expirada. Faça login novamente.");
  }
  return res;
}

// ===== Autenticação / UI =====
const auth = { token: getToken(), user: null };
function authHeader(){ return auth.token ? { Authorization: "Bearer " + auth.token } : {}; }

// --- permissões
function canAccess(section){
  if (auth?.user?.role === "admin") return true;
  const perms = auth?.user?.permissions || [];
  return perms.includes(section);
}

function applyRoleUI(){
  // esconde itens do menu conforme o data-view -> perm
  const viewToPerm = { vendas:"vendas", produtos:"produtos", administracao:"administracao" };
  $$(".sidebar a").forEach(a=>{
    const req = viewToPerm[a.dataset.view] || null;
    a.style.display = req ? (canAccess(req) ? "" : "none") : "";
  });
}

function showView(name){
  // impede abrir view sem permissão
  const guardMap = {
    dashboard: null,
    vendas: "vendas",
    produtos: "produtos",
    administracao: "administracao",
    historico: null,
  };
  const need = guardMap[name] || null;
  if (need && !canAccess(need)){ alert("Sem permissão para acessar esta seção."); return; }

  ["view-dashboard","tab-pdv","tab-historico","view-produtos","view-admin"].forEach(id=>{
    const el = $("#"+id);
    if (!el) return;
    el.classList.add("is-hidden");
    el.setAttribute("aria-hidden","true");
  });
  const map = {
    dashboard: "#view-dashboard",
    vendas: "#tab-pdv",
    historico: "#tab-historico",
    produtos: "#view-produtos",
    administracao: "#view-admin",
  };
  const sel = map[name]; if (!sel) return;
  const node = $(sel); if (node){
    node.classList.remove("is-hidden");
    node.setAttribute("aria-hidden","false");
  }
  if (name === "administracao") loadUsers();
}

function setLoggedIn(user, token){
  auth.user = user;
  auth.token = token || null;
  setToken(token || null);

  const info = $("#userInfo"); if (info) info.textContent = user ? `Logado como: ${user.username} (${user.role})` : "";
  const btnLogout = $("#logoutBtn"); if (btnLogout) btnLogout.classList.toggle("is-hidden", !user);
  const loginScreen = $("#loginScreen"); if (loginScreen) loginScreen.classList.toggle("is-hidden", !!user);
  const appLayout = $("#appLayout"); if (appLayout) {
    appLayout.classList.toggle("is-hidden", !user);
    appLayout.setAttribute("aria-hidden", user ? "false" : "true");
  }

  if (user){
    applyRoleUI();
    // escolhe a primeira aba permitida
    const firstAllowed = $$(".sidebar a").find(a => a.style.display !== "none");
    if (firstAllowed){
      $$(".sidebar a").forEach(x=>x.classList.remove("active"));
      firstAllowed.classList.add("active");
      const vt = $("#viewTitle"); if (vt) vt.textContent = firstAllowed.textContent;
      showView(firstAllowed.dataset.view);
    }else{
      showView("dashboard");
    }
  }
}
on($("#logoutBtn"), "click", () => setLoggedIn(null, null));

// ===== Navegação lateral =====
$$(".sidebar a").forEach(a => on(a, "click", e=>{
  e.preventDefault();
  if (a.style.display === "none") return; // bloqueia clique em item oculto
  $$(".sidebar a").forEach(x=>x.classList.remove("active"));
  a.classList.add("active");
  const vt = $("#viewTitle"); if (vt) vt.textContent = a.textContent;

  const v = a.dataset.view;
  if (v === "dashboard")      { showView("dashboard"); }
  if (v === "vendas")         { showView("vendas"); }
  if (v === "produtos")       { showView("produtos"); }
  if (v === "administracao")  { showView("administracao"); }
}));

// ===== Dashboard =====
const dashState = { start:null, end:null };

function setPreset(p){
  const t = new Date(); let s, e;
  if (p==="today"){ s=e=t; }
  else if (p==="yesterday"){ const y = new Date(t); y.setDate(t.getDate()-1); s=e=y; }
  else if (p==="7d"){ e=t; s=new Date(t); s.setDate(t.getDate()-6); }
  else if (p==="30d"){ e=t; s=new Date(t); s.setDate(t.getDate()-29); }
  else if (p==="month"){ e=t; s=new Date(t.getFullYear(), t.getMonth(), 1); }
  const ds = $("#dashStart"); if (ds) ds.value = fmtDate(s);
  const de = $("#dashEnd");   if (de) de.value = fmtDate(e);
}
on($("#dashApply"), "click", ()=>{
  const ds = $("#dashStart"), de = $("#dashEnd");
  dashState.start = ds ? ds.value : null;
  dashState.end   = de ? de.value : null;
  refreshDashboard();
});
$$(".chip").forEach(c=> on(c, "click", ()=>{ setPreset(c.dataset.range); $("#dashApply")?.click(); }));

async function refreshDashboard(){
  try{
    const qs = `?start=${encodeURIComponent(dashState.start||"")}&end=${encodeURIComponent(dashState.end||"")}`;
    const r1 = await api("/api/dashboard/summary"+qs); const s = await r1.json();
    const k = s.kpis || {};
    const set = (id,val)=>{ const el=$("#"+id); if (el) el.textContent = val; };
    set("kpiOrders", k.orders||0);
    set("kpiRevenue", currency(k.revenue||0));
    set("kpiAvg", currency(k.avg_ticket||0));
    set("kpiMonth", currency(k.month_revenue||0));

    const r2 = await api("/api/dashboard/latest_sales"+qs); const ls = await r2.json();
    const tb = $("#tblLatest tbody"); if (tb){ tb.innerHTML=""; (ls.items||[]).forEach(v=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${v.id}</td><td>${new Date(v.created_at).toLocaleString("pt-BR")}</td><td>${v.channel||"-"}</td><td>${v.payment||"-"}</td><td>R$ ${currency(v.total||0)}</td>`;
      tb.appendChild(tr);
    });}

    const r3 = await api("/api/dashboard/top_products"+qs); const tp = await r3.json();
    const tpTb = $("#tblTopProducts tbody"); if (tpTb){ tpTb.innerHTML=""; (tp.items||[]).forEach(p=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${p.name}</td><td>${p.qty}</td><td>R$ ${currency(p.revenue||0)}</td>`;
      tpTb.appendChild(tr);
    });}
  }catch{/* silencioso */}
}
on($("#goSales"), "click", ()=> { showView("vendas"); });
on($("#btnCsv"), "click", async ()=>{
  const qs = `?start=${encodeURIComponent(dashState.start||"")}&end=${encodeURIComponent(dashState.end||"")}`;
  const r = await api("/api/dashboard/export/sales.csv"+qs);
  const blob = await r.blob(); const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = "sales.csv"; a.click(); URL.revokeObjectURL(url);
});

// ===== PDV =====
const state = { items:[], subtotal:0, total:0 };

function recalc(){
  state.subtotal = state.items.reduce((s,it)=> s + it.qty*it.price, 0);
  const frete = parseFloat($("#frete")?.value || 0);
  const descV = parseFloat($("#descontoValor")?.value || 0);
  const descP = parseFloat($("#descontoPct")?.value || 0);
  const desc  = descV + (state.subtotal * (descP/100));
  state.total = Math.max(0, state.subtotal + frete - desc);

  $("#subtotal") && ($("#subtotal").textContent = currency(state.subtotal));
  $("#total")    && ($("#total").textContent    = currency(state.total));

  const recebido = parseFloat($("#recebido")?.value || 0);
  $("#troco") && ($("#troco").textContent = currency(Math.max(0, recebido - state.total)));
}

function renderItems(){
  const tb = $("#itensTable tbody"); if (!tb) return;
  tb.innerHTML = "";
  state.items.forEach((it, idx)=>{
    const img = it.image_url ? `<img src="${it.image_url}" alt="" style="width:34px;height:34px;object-fit:cover;border-radius:6px;margin-right:.5rem;">` : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><div style="display:flex;align-items:center;">${img}<span>${it.name}</span></div></td>
      <td>${it.variant || "-"}</td>
      <td><input type="number" min="1" step="1" value="${it.qty}" data-idx="${idx}"></td>
      <td>${currency(it.price)}</td>
      <td>${currency(it.qty * it.price)}</td>
      <td><button class="btn" data-remove="${idx}">✕</button></td>`;
    tb.appendChild(tr);
  });
  recalc();
}

function showPdvError(msg){
  const el = $("#pdvError");
  if (el){
    el.textContent = msg;
    el.classList.remove("is-hidden");
    setTimeout(()=> el.classList.add("is-hidden"), 4000);
  }else{
    alert(msg);
  }
}

function addOrIncrementItem(prod, qty = 1, priceOverride = null){
  const price = Number(priceOverride !== null ? priceOverride : (prod.price || 0));
  const keyVariant = prod.variant ?? "-";
  const idx = state.items.findIndex(it => it.sku === prod.sku && (it.variant ?? "-") === keyVariant);
  if (idx >= 0){
    state.items[idx].qty += Number(qty);
  }else{
    state.items.push({
      id: prod.id,
      sku: prod.sku,
      name: prod.name,
      image_url: prod.image_url || null,
      variant: keyVariant,
      qty: Number(qty || 1),
      price,
    });
  }
  renderItems();
}

// submit do formulário de bipagem
on($("#scanForm"), "submit", async (e)=>{
  e.preventDefault();
  await pdvFindAndAdd();
});

async function pdvFindAndAdd(){
  const codeInput = $("#pdvCode");
  const qtyInput  = $("#pdvQty");
  const priceInp  = $("#pdvPrice");
  const btnAdd    = $("#scanForm button[type='submit']");

  const code = (codeInput?.value || "").trim();
  const qty  = Number(qtyInput?.value || 1);
  const pOv  = priceInp?.value?.trim() ? Number(priceInp.value) : null;

  if (!code){ showPdvError("Informe um código/SKU para adicionar."); return; }

  if (btnAdd) btnAdd.disabled = true;

  const res = await apiFetch(`/api/products/find?query=${encodeURIComponent(code)}`, { returnResponse: true });

  if (res.status === 200){
    const prod = await res.json();
    addOrIncrementItem(prod, qty, pOv);
    if (codeInput){ codeInput.value = ""; codeInput.focus(); }
    if (priceInp) priceInp.value = "";
  }else if (res.status === 404){
    showPdvError("Produto não encontrado. Cadastre no inventário primeiro.");
  }else if (res.status === 400 || res.status === 422){
    showPdvError("Código inválido. Verifique o SKU/EAN.");
  }else if (res.status === 401){
    showPdvError("Sessão expirada. Faça login novamente.");
    setLoggedIn(null, null);
  }else{
    const msg = await res.text().catch(()=> "");
    showPdvError(`Erro ao consultar produto: ${res.status} ${msg || ""}`);
  }

  if (btnAdd) btnAdd.disabled = false;
}

// atalhos
on(document, "keydown", e=>{
  if (e.altKey && (e.key === "d" || e.key === "D")){ e.preventDefault(); toggleTheme(); }
  if (e.key === "Escape") { closeHistoryOverlay(); }
  if (e.ctrlKey && e.key === "Backspace"){ e.preventDefault(); state.items = []; renderItems(); }
});
on($("#itensTable"), "input", e=>{
  const idx = e.target?.dataset?.idx;
  if (idx !== undefined){
    state.items[idx].qty = Math.max(1, parseInt(e.target.value || "1", 10));
    renderItems();
  }
});
on($("#itensTable"), "click", e=>{
  const idx = e.target?.dataset?.remove;
  if (idx !== undefined){
    state.items.splice(parseInt(idx, 10), 1);
    renderItems();
  }
});
on($("#aplicarDesconto"), "click", e=>{ e.preventDefault(); recalc(); });
["descontoValor","descontoPct","frete","recebido"].forEach(id => on($("#"+id), "input", recalc));

on($("#fecharVenda"), "click", async e=>{
  e.preventDefault();
  if (state.items.length === 0) return alert("Adicione ao menos 1 item.");
  const payload = {
    client_name: $("#clienteInput")?.value || null,
    payment:     $("#pagamento")?.value || null,
    installments: parseInt($("#parcelas")?.value || "1", 10),
    discount_value: parseFloat($("#descontoValor")?.value || 0),
    discount_pct:   parseFloat($("#descontoPct")?.value || 0),
    freight:        parseFloat($("#frete")?.value || 0),
    received:       parseFloat($("#recebido")?.value || 0),
    subtotal: state.subtotal,
    total: state.total,
    items: state.items
  };
  try{
    const r = await api("/api/sales", { method: "POST", body: JSON.stringify(payload) });
    const d = await r.json();
    alert("Venda #"+d.id+" registrada!");
    state.items = []; renderItems();
  }catch{ alert("Erro ao fechar venda."); }
});

// ===== Produtos (CRUD + Imagem) =====
on($("#productForm"), "submit", async e=>{
  e.preventDefault();
  const id = $("#prodId")?.value || null;

  // imagem atual (se existir)
  let image_url = $("#prodImageUrl")?.value || null;

  // se um novo arquivo foi selecionado, faz upload primeiro
  const fileInp = $("#prodImage");
  const file = fileInp?.files?.[0] || null;
  if (file){
    try{
      const up = await uploadFile("/api/upload/product-image", file);
      image_url = up.url;
    }catch(err){
      alert("Upload da imagem: " + err.message);
      return;
    }
  }

  const payload = {
    sku:     $("#prodSku")?.value.trim() || "",
    name:    $("#prodName")?.value.trim() || "",
    variant: $("#prodVariant")?.value.trim() || null,
    price:   parseFloat($("#prodPrice")?.value || "0"),
    image_url: image_url || null,
  };

  try{
    let r;
    if (id) r = await api(`/api/products/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    else    r = await api("/api/products",        { method: "POST", body: JSON.stringify(payload) });
    if (!r.ok) throw new Error(await r.text());

    // limpar form
    $("#clearProd")?.click();
    if ($("#prodImage")) $("#prodImage").value = "";
    if ($("#prodImagePreview")) $("#prodImagePreview").src = "";
    if ($("#prodImageUrl")) $("#prodImageUrl").value = "";

    await loadProducts();
  }catch(err){ alert("Salvar produto: " + err.message); }
});

on($("#clearProd"), "click", ()=>{
  ["prodId","prodSku","prodName","prodVariant","prodPrice","prodImageUrl"].forEach(id=>{ const el=$("#"+id); if (el) el.value=""; });
  if ($("#prodImage")) $("#prodImage").value = "";
  if ($("#prodImagePreview")) $("#prodImagePreview").src = "";
});

on($("#reloadProds"), "click", loadProducts);
on($("#prodSearch"), "input", ()=> loadProducts());

// preview instantâneo ao escolher arquivo
on($("#prodImage"), "change", ()=>{
  const f = $("#prodImage")?.files?.[0];
  if (!f) return;
  const url = URL.createObjectURL(f);
  const img = $("#prodImagePreview");
  if (img) img.src = url;
});

async function loadProducts(){
  try{
    const q = $("#prodSearch")?.value.trim() || "";
    const r = await api("/api/products?limit=50&query="+encodeURIComponent(q));
    const d = await r.json();
    const tb = $("#prodTable tbody"); if (!tb) return;
    tb.innerHTML = "";
    (d.items||[]).forEach(p=>{
      const thumb = p.image_url ? `<img src="${p.image_url}" alt="" style="width:34px;height:34px;object-fit:cover;border-radius:6px;margin-right:.5rem;">` : "";
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${p.id}</td>
         <td>${p.sku}</td>
         <td><div style="display:flex;align-items:center;">${thumb}<span>${p.name}</span></div></td>
         <td>${p.variant||"-"}</td>
         <td>${currency(p.price)}</td>
         <td><button class="btn" data-edit="${p.id}">Editar</button> <button class="btn danger" data-del="${p.id}">Excluir</button></td>`;
      tb.appendChild(tr);
    });
  }catch{}
}

on($("#prodTable"), "click", async e=>{
  const t = e.target || {};
  const idE = t.dataset?.edit;
  const idD = t.dataset?.del;
  if (idE){
    const r = await api(`/api/products/${idE}`);
    if (r.ok){
      const p = await r.json();
      $("#prodId").value = p.id;
      $("#prodSku").value = p.sku;
      $("#prodName").value = p.name;
      $("#prodVariant").value = p.variant || "";
      $("#prodPrice").value = p.price;
      if ($("#prodImageUrl")) $("#prodImageUrl").value = p.image_url || "";
      if ($("#prodImagePreview")) $("#prodImagePreview").src = p.image_url || "";
      if ($("#prodImage")) $("#prodImage").value = ""; // limpa seleção anterior
    }
  }
  if (idD){
    if (!confirm("Excluir produto "+idD+"?")) return;
    const r = await api(`/api/products/${idD}`, { method: "DELETE" });
    if (r.ok) loadProducts(); else alert("Não foi possível excluir.");
  }
});

// ===== Histórico (Overlay) =====
const histState = { start:null, end:null };

function ensureHistoryOverlay(){
  if ($("#historyOverlay")) return;
  const el = document.createElement("div");
  el.id = "historyOverlay";
  el.className = "is-hidden";
  el.setAttribute("aria-hidden","true");
  el.style.cssText = `
    position:fixed; inset:0; background:rgba(0,0,0,.45); display:flex; align-items:flex-start; justify-content:center; padding:2rem; z-index:9999;
  `;
  el.innerHTML = `
    <div class="card span-6" role="dialog" aria-modal="true" aria-label="Histórico de Vendas" style="max-width:1000px; width:100%; box-shadow:0 20px 60px rgba(0,0,0,.35);">
      <div class="card-title" style="display:flex;align-items:center;justify-content:space-between;">
        <span>Histórico de Vendas</span>
        <div class="combo">
          <button id="btnCloseHistory" class="btn" type="button">Fechar</button>
        </div>
      </div>

      <div class="combo" style="flex-wrap:wrap; gap:.5rem; padding:0 .75rem .5rem;">
        <div class="chip-group" role="group" aria-label="Atalhos de período">
          <button class="chip" data-hist-range="today" type="button">Hoje</button>
          <button class="chip" data-hist-range="yesterday" type="button">Ontem</button>
          <button class="chip" data-hist-range="7d" type="button">7 dias</button>
        </div>
        <div class="combo">
          <label class="label" for="histStart">De</label>
          <input id="histStart" type="date" autocomplete="off">
        </div>
        <div class="combo">
          <label class="label" for="histEnd">até</label>
          <input id="histEnd" type="date" autocomplete="off">
        </div>
        <button id="histApply" class="btn primary" type="button">Aplicar</button>
      </div>

      <div id="historyList" class="list" style="padding:.5rem .75rem 1rem;"></div>
    </div>
  `;
  document.body.appendChild(el);

  // clicar fora fecha
  el.addEventListener("click", (ev)=>{
    if (ev.target === el) closeHistoryOverlay();
  });
}

function initHistoryFilters(){
  const t = new Date();
  const s = fmtDate(t), e = fmtDate(t);
  if ($('#histStart')) $('#histStart').value = s;
  if ($('#histEnd'))   $('#histEnd').value   = e;
  histState.start = s;
  histState.end   = e;
}

function setHistPreset(preset){
  const t = new Date(); let s, e;
  if (preset === 'today'){ s=e=t; }
  else if (preset === 'yesterday'){ const y=new Date(t); y.setDate(t.getDate()-1); s=e=y; }
  else if (preset === '7d'){ e=t; s=new Date(t); s.setDate(t.getDate()-6); }
  $('#histStart').value = fmtDate(s);
  $('#histEnd').value   = fmtDate(e);
  histState.start = $('#histStart').value;
  histState.end   = $('#histEnd').value;
  loadHistoryRange();
}

on(document, 'click', (e)=>{
  const btn = e.target.closest('[data-hist-range]');
  if (btn) setHistPreset(btn.getAttribute('data-hist-range'));
});

on(document, 'click', (e)=>{
  if (e.target && e.target.id === 'histApply') {
    histState.start = $('#histStart')?.value || null;
    histState.end   = $('#histEnd')?.value || null;
    loadHistoryRange();
  }
});

async function loadHistoryRange(){
  try{
    const qs = `?start=${encodeURIComponent(histState.start||'')}&end=${encodeURIComponent(histState.end||'')}&limit=500`;
    const res = await api('/api/dashboard/latest_sales'+qs);
    const data = await res.json();
    renderHistoryList(data.items || []);
  }catch{
    renderHistoryList([]);
  }
}

function renderHistoryList(items){
  const list = $('#historyList');
  if (!list) return;
  list.innerHTML = '';
  if (!items.length){
    const empty = document.createElement('div');
    empty.className = 'muted small';
    empty.textContent = 'Sem vendas no período selecionado.';
    list.appendChild(empty);
    return;
  }
  items.forEach(v=>{
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <strong>Venda #${v.id}</strong> — ${new Date(v.created_at).toLocaleString('pt-BR')}
      <div class="muted small">Canal: ${v.channel || 'PDV'} • Pagamento: ${v.payment || '-'}</div>
      <div>Total: R$ ${currency(v.total || 0)}</div>`;
    list.appendChild(card);
  });
}

function openHistoryOverlay(){
  ensureHistoryOverlay();
  initHistoryFilters();
  loadHistoryRange();
  const ov = $('#historyOverlay'); if (!ov) return;
  ov.classList.remove('is-hidden'); ov.setAttribute('aria-hidden','false');
  document.body.style.overflow = 'hidden';
}
function closeHistoryOverlay(){
  const ov = $('#historyOverlay'); if (!ov) return;
  ov.classList.add('is-hidden'); ov.setAttribute('aria-hidden','true');
  document.body.style.overflow = '';
}

// Botão “Histórico” do PDV
on($('#btnOpenHistory'), 'click', openHistoryOverlay);
// Botão “Fechar” do overlay (delegação)
document.addEventListener('click', (e)=>{
  if (e.target && e.target.id === 'btnCloseHistory') closeHistoryOverlay();
});

// ===== Login =====
on($("#loginForm"), "submit", async (e)=>{
  e.preventDefault();
  const username = $("#loginUser")?.value.trim() || "";
  const password = $("#loginPass")?.value || "";
  try{
    const res = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
    setLoggedIn(res.user, res.access_token);
    await initAfterLogin();
  }catch(err){ alert("Login: " + err.message); }
});

on($("#firstAdminBtn"), "click", async ()=>{
  const username = $("#loginUser")?.value.trim() || "";
  const password = $("#loginPass")?.value || "";
  if (!username || !password) return alert("Preencha usuário e senha");
  try{
    await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password, role: "admin" })
    });
    alert("Admin criado. Agora faça login.");
  }catch(err){ alert("Registro: " + err.message); }
});

// ===== Pós-login =====
async function initAfterLogin(){
  setPreset("today");
  const ds = $("#dashStart"), de = $("#dashEnd");
  dashState.start = ds ? ds.value : null;
  dashState.end   = de ? de.value : null;
  ensureHistoryOverlay();
  await Promise.all([ refreshDashboard(), loadProducts() ]);
  await loadClients();
}

// ===== Administração: Usuários & Permissões =====
function getPermsFromForm(){
  return $$(".admperm").filter(x=> x.checked).map(x=> x.value);
}
function setPermsInForm(perms){
  const set = new Set(perms || []);
  $$(".admperm").forEach(x=> x.checked = set.has(x.value));
}

async function loadUsers(){
  if (!$("#adminUsersTable")) return;
  try{
    const r = await api("/api/admin/users");
    const users = await r.json();
    const tb = $("#adminUsersTable tbody"); if (!tb) return;
    tb.innerHTML = "";
    users.forEach(u=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${u.id}</td>
        <td>${u.username}</td>
        <td>${u.role}</td>
        <td>${(u.permissions||[]).join(", ")||"-"}</td>
        <td>
          <button class="btn" data-edit-user="${u.id}">Editar</button>
          <button class="btn danger" data-del-user="${u.id}">Excluir</button>
        </td>`;
      tb.appendChild(tr);
    });
  }catch{}
}

on($("#adminReload"), "click", loadUsers);
on($("#adminClear"), "click", ()=>{
  ["admId","admUser","admPass"].forEach(id=> { const el=$("#"+id); if (el) el.value=""; });
  if ($("#admRole")) $("#admRole").value = "operator";
  setPermsInForm([]);
});

on($("#adminForm"), "submit", async (e)=>{
  if (!$("#adminForm")) return;
  e.preventDefault();
  const id = $("#admId")?.value || null;
  const payload = {
    username: $("#admUser")?.value.trim(),
    password: $("#admPass")?.value || null,
    role: $("#admRole")?.value || "operator",
    permissions: getPermsFromForm(),
  };
  if (!payload.username){ alert("Informe um usuário"); return; }
  try{
    let r;
    if (id){
      r = await api(`/api/admin/users/${id}`, { method:"PUT", body: JSON.stringify(payload) });
    }else{
      if (!payload.password){ alert("Informe a senha"); return; }
      r = await api("/api/admin/users", { method:"POST", body: JSON.stringify(payload) });
    }
    if (!r.ok) throw new Error(await r.text());
    $("#adminClear")?.click();
    await loadUsers();
    alert("Usuário salvo com sucesso.");
  }catch(err){ alert("Salvar usuário: " + err.message); }
});

on($("#adminUsersTable"), "click", async (e)=>{
  const t = e.target || {};
  const idE = t.dataset?.editUser;
  const idD = t.dataset?.delUser;
  if (idE){
    // Busca os dados do usuário na tabela (sem chamada extra)
    const row = t.closest("tr");
    const id = row.children[0].textContent;
    const username = row.children[1].textContent;
    const role = row.children[2].textContent;
    const perms = row.children[3].textContent.split(",").map(s=>s.trim()).filter(Boolean);

    $("#admId").value = id;
    $("#admUser").value = username;
    $("#admPass").value = "";
    $("#admRole").value = role;
    setPermsInForm(perms);
  }
  if (idD){
    if (!confirm("Excluir usuário "+idD+"?")) return;
    const r = await api(`/api/admin/users/${idD}`, { method:"DELETE" });
    if (r.ok) loadUsers(); else alert("Não foi possível excluir.");
  }
});

// ===== Clientes (lista simples para datalist) =====
async function loadClients(){
  try{
    const r = await api("/api/clients?limit=50"); const d = await r.json();
    const dl = $("#clientes"); if (!dl) return;
    dl.innerHTML = "";
    (d.items||[]).forEach(c=>{ const o=document.createElement("option"); o.value=c.name; dl.appendChild(o); });
  }catch{}
}

// Boot: tenta restaurar sessão
(async function boot(){
  if (getToken()){
    try{
      const r = await apiFetch("/api/auth/me");
      setLoggedIn(r, getToken());
      await initAfterLogin();
      return;
    }catch{ /* segue para login */ }
  }
  setLoggedIn(null, null);
})();
