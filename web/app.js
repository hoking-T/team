/* 智慧仓储物流协同系统 - 前端逻辑（原生 JS，无第三方依赖） */
const API_BASE = '';
let TOKEN = localStorage.getItem('wms_token') || '';
let ME = null;
let state = { view: 'dashboard', tab: {} };
const cache = { warehouses: [], locations: [], products: [], suppliers: [], roles: [] };

/* ---------------- 基础工具 ---------------- */
async function api(path, method = 'GET', body) {
  const opt = { method, headers: { 'Content-Type': 'application/json' } };
  if (TOKEN) opt.headers['Authorization'] = 'Bearer ' + TOKEN;
  if (body) opt.body = JSON.stringify(body);
  const res = await fetch(API_BASE + path, opt);
  let json;
  try { json = await res.json(); } catch (e) { throw new Error('服务响应异常'); }
  if (!res.ok || json.ok === false) {
    if (res.status === 401) { doLogout(true); }
    throw new Error(json.msg || ('请求失败 ' + res.status));
  }
  return json.data;
}

function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function money(n) { return (Number(n) || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function fmtTime(t) { return t ? esc(t) : '-'; }

const STATUS_COLOR = {
  '待收货': 'amber', '收货中': 'amber', '待上架': 'blue', '已完成': 'green', '已取消': 'red',
  '待拣货': 'amber', '拣货中': 'blue', '待复核': 'blue', '待出库': 'amber', '已出库': 'green',
  '待录入': 'amber', '待审核': 'blue', '待推送': 'amber', '推送失败': 'red', '已推送': 'green', '已签收': 'teal'
};
function tag(status) {
  const c = STATUS_COLOR[status] || '';
  return `<span class="tag ${c}">${esc(status)}</span>`;
}

function toast(msg, type = 'ok') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type;
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => t.classList.add('hidden'), 2600);
}

/* ---------------- 弹窗 ---------------- */
let modalOk = null;
function openModal({ title, body, okText = '确定', onOk, width = '', cancelText = '取消' }) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = body;
  const foot = document.getElementById('modal-foot');
  foot.innerHTML = '';
  if (cancelText) {
    const c = document.createElement('button');
    c.className = 'btn'; c.textContent = cancelText; c.onclick = closeModal;
    foot.appendChild(c);
  }
  if (onOk) {
    const b = document.createElement('button');
    b.className = 'btn btn-primary'; b.textContent = okText;
    b.onclick = async () => {
      b.disabled = true; b.textContent = '处理中...';
      try { await onOk(); } catch (e) { toast(e.message, 'err'); b.disabled = false; b.textContent = okText; }
    };
    foot.appendChild(b);
  }
  const m = document.querySelector('.modal');
  m.className = 'modal' + (width === 'wide' ? ' wide' : '');
  document.getElementById('modal-mask').classList.remove('hidden');
}
function closeModal() { document.getElementById('modal-mask').classList.add('hidden'); modalOk = null; }

/* ---------------- 登录 ---------------- */
async function doLogin() {
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-pwd').value.trim();
  if (!username || !password) return toast('请输入账号和密码', 'err');
  try {
    const d = await api('/api/login', 'POST', { username, password });
    TOKEN = d.token; localStorage.setItem('wms_token', TOKEN); ME = d.user;
    enterApp();
  } catch (e) { toast(e.message, 'err'); }
}

function doLogout(silent) {
  TOKEN = ''; localStorage.removeItem('wms_token'); ME = null;
  document.getElementById('app').classList.add('hidden');
  document.getElementById('login-page').classList.remove('hidden');
  if (!silent) toast('已退出登录');
}
function logout() { fetch('/api/logout', { method: 'POST' }).catch(() => { }); doLogout(false); }

document.getElementById('login-btn').onclick = doLogin;
document.getElementById('login-pwd').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });

/* ---------------- 主框架 ---------------- */
const MENU = [
  { key: 'dashboard', name: '工作台', ico: '▦', perm: 'dashboard', sub: '实时掌握仓储作业与物流协同状态' },
  { key: 'master', name: '基础数据', ico: '▤', perm: 'master', sub: '仓库、库位、商品 SKU 与供应商维护' },
  { key: 'inbound', name: '入库管理', ico: '↓', perm: 'inbound', sub: '到货登记 → 收货验货 → 上架确认' },
  { key: 'inventory', name: '库存管理', ico: '▣', perm: 'inventory', sub: '实时库存、库存预警、盘点与库存流水' },
  { key: 'picking', name: '拣选作业', ico: '✓', perm: 'picking', sub: '拣货任务分配与扫码确认' },
  { key: 'outbound', name: '出库与物流', ico: '↑', perm: 'outbound', sub: '出库单、复核出库、运单推送与轨迹跟踪' },
  { key: 'system', name: '系统管理', ico: '⚙', perm: 'system', sub: '用户、角色权限、业务事件与操作日志' }
];

function enterApp() {
  document.getElementById('login-page').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  const nav = document.getElementById('nav');
  nav.innerHTML = MENU.filter(m => ME.permissions.includes(m.perm)).map(m =>
    `<div class="nav-item" data-key="${m.key}"><span class="nav-ico">${m.ico}</span>${m.name}</div>`).join('');
  nav.querySelectorAll('.nav-item').forEach(el => el.onclick = () => go(el.dataset.key));
  document.getElementById('side-user').innerHTML = `<b>${esc(ME.name)}</b> · ${esc(ME.roleName)}<br>账号 ${esc(ME.username)}`;
  go(MENU.find(m => ME.permissions.includes(m.perm)).key);
  setInterval(() => { document.getElementById('clock').textContent = new Date().toLocaleString('zh-CN'); }, 1000);
}

function go(key) {
  if (!ME) return;
  state.view = key;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.key === key));
  const m = MENU.find(x => x.key === key);
  document.getElementById('view-title').textContent = m.name;
  document.getElementById('view-sub').textContent = m.sub;
  const box = document.getElementById('view');
  box.innerHTML = '<div class="empty">加载中...</div>';
  const fn = VIEWS[key];
  if (fn) fn(box).catch(e => { box.innerHTML = `<div class="empty">加载失败：${esc(e.message)}</div>`; });
}

/* ---------------- 通用表格 ---------------- */
function table(cols, rows, actions) {
  if (!rows || !rows.length) return '<div class="empty">暂无数据</div>';
  const head = cols.map(c => `<th>${c.title}</th>`).join('') + (actions ? '<th style="width:1%">操作</th>' : '');
  const body = rows.map((r, i) => {
    const tds = cols.map(c => `<td>${c.render ? c.render(r, i) : esc(r[c.key])}</td>`).join('');
    const act = actions ? `<td style="white-space:nowrap">${actions(r, i)}</td>` : '';
    return `<tr>${tds}${act}</tr>`;
  }).join('');
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

async function loadBase() {
  const [w, p, s] = await Promise.all([api('/api/warehouses'), api('/api/products'), api('/api/suppliers')]);
  cache.warehouses = w; cache.products = p; cache.suppliers = s;
  cache.locations = await api('/api/locations');
}
function whOptions(selected) {
  return cache.warehouses.map(w => `<option value="${w.id}" ${selected == w.id ? 'selected' : ''}>${esc(w.name)}</option>`).join('');
}
function prodOptions(selected) {
  return cache.products.map(p => `<option value="${p.id}" ${selected == p.id ? 'selected' : ''}>${esc(p.sku)} ${esc(p.name)}</option>`).join('');
}
function locOptions(whId, selected) {
  return cache.locations.filter(l => !whId || l.warehouse_id == whId).map(l =>
    `<option value="${l.id}" ${selected == l.id ? 'selected' : ''}>${esc(l.code)}（${esc(l.zone || '')}）</option>`).join('');
}

/* ================================================================ 工作台 */
const VIEWS = {};

VIEWS.dashboard = async (box) => {
  const d = await api('/api/dashboard');
  const c = d.cards;
  box.innerHTML = `
  <div class="stat-grid">
    <div class="stat"><div class="lbl">库存总量</div><div class="val">${c.stockTotal.toLocaleString('zh-CN')}<span class="unit">件</span></div></div>
    <div class="stat blue"><div class="lbl">仓库 / 库位</div><div class="val">${c.warehouses} / ${c.locations}<span class="unit">个</span></div></div>
    <div class="stat amber"><div class="lbl">待处理入库单</div><div class="val">${c.pendingInbound}<span class="unit">单</span></div></div>
    <div class="stat amber"><div class="lbl">待处理出库单 / 拣货任务</div><div class="val">${c.pendingOutbound} / ${c.pendingPick}<span class="unit">单</span></div></div>
    <div class="stat red"><div class="lbl">库存预警 SKU</div><div class="val">${c.warnCount}<span class="unit">个</span></div></div>
    <div class="stat"><div class="lbl">盘点中单据</div><div class="val">${c.pendingCheck}<span class="unit">单</span></div></div>
    <div class="stat blue"><div class="lbl">商品 SKU 数</div><div class="val">${c.skus}<span class="unit">个</span></div></div>
    <div class="stat"><div class="lbl">业务事件总数</div><div class="val" id="ev-count">-</div></div>
  </div>
  <div class="two-col">
    <div class="card">
      <div class="card-head"><h3>库存预警（低于安全库存）</h3><span class="hint">低于安全库存自动预警</span></div>
      ${table([
        { title: 'SKU', key: 'sku' }, { title: '商品名称', key: 'name' },
        { title: '当前库存', render: r => `<b style="color:#b91c1c">${r.qty}</b>` },
        { title: '安全库存', key: 'warn_threshold' }
      ], d.warnings)}
    </div>
    <div class="card">
      <div class="card-head"><h3>业务事件流（事件驱动）</h3><span class="hint">最新 8 条</span></div>
      ${d.events.map(e => `<div class="event-item">
          <span class="t">${esc(e.created_at.slice(5, 16))}</span>
          <span class="e">${esc(e.event_type)}</span>
          <span class="p">${esc(e.aggregate_id)}</span></div>`).join('') || '<div class="empty">暂无事件</div>'}
    </div>
  </div>`;
  // 修正第 7 个卡片
  const stats = box.querySelectorAll('.stat')[6];
  stats.innerHTML = `<div class="lbl">商品 SKU 数</div><div class="val">${c.skus}<span class="unit">个</span></div>`;
  const evc = document.getElementById('ev-count');
  if (evc) { const evs = await api('/api/events'); evc.innerHTML = evs.length + '<span class="unit">条(近100)</span>'; }
};

/* ================================================================ 基础数据 */
VIEWS.master = async (box) => {
  await loadBase();
  const tab = state.tab.master || 'warehouses';
  box.innerHTML = `
  <div class="tabs">
    ${[['warehouses', '仓库'], ['locations', '库位'], ['products', '商品 SKU'], ['suppliers', '供应商']]
      .map(([k, n]) => `<div class="tab ${tab === k ? 'active' : ''}" data-tab="${k}">${n}</div>`).join('')}
  </div>
  <div id="master-body"></div>`;
  box.querySelectorAll('.tab').forEach(el => el.onclick = () => { state.tab.master = el.dataset.tab; VIEWS.master(box); });
  const body = document.getElementById('master-body');

  if (tab === 'warehouses') {
    const rows = await api('/api/warehouses');
    body.innerHTML = `<div class="toolbar"><button class="btn btn-primary" id="add-wh">新增仓库</button></div>
      <div class="card">${table([
        { title: '编码', key: 'code' }, { title: '仓库名称', key: 'name' },
        { title: '地址', key: 'address' }, { title: '负责人', key: 'manager' },
        { title: '状态', render: r => r.status ? tag('已启用') : tag('已停用') }
      ], rows, r => `<button class="btn-link danger" data-del="${r.id}">删除</button>`)}</div>`;
    document.getElementById('add-wh').onclick = () => openModal({
      title: '新增仓库',
      body: `<div class="form-grid">
        <div class="form-item"><label>仓库编码<span class="req">*</span></label><input id="f-code" placeholder="如 WH03"></div>
        <div class="form-item"><label>仓库名称<span class="req">*</span></label><input id="f-name" placeholder="如 天津二号仓"></div>
        <div class="form-item full"><label>地址</label><input id="f-addr"></div>
        <div class="form-item"><label>负责人</label><input id="f-mgr"></div></div>`,
      onOk: async () => {
        await api('/api/warehouses', 'POST', {
          code: document.getElementById('f-code').value.trim(),
          name: document.getElementById('f-name').value.trim(),
          address: document.getElementById('f-addr').value.trim(),
          manager: document.getElementById('f-mgr').value.trim()
        });
        closeModal(); toast('仓库已创建'); VIEWS.master(box);
      }
    });
    body.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
      if (!confirm('确定删除该仓库？')) return;
      try { await api('/api/warehouses/' + b.dataset.del, 'DELETE'); toast('已删除'); VIEWS.master(box); }
      catch (e) { toast(e.message, 'err'); }
    });
  }

  if (tab === 'locations') {
    const rows = await api('/api/locations');
    body.innerHTML = `<div class="toolbar"><button class="btn btn-primary" id="add-loc">新增库位</button>
      <span class="hint">共 ${rows.length} 个库位</span></div>
      <div class="card">${table([
        { title: '仓库', key: 'warehouse_name' }, { title: '库位编码', key: 'code' },
        { title: '区域', key: 'zone' }, { title: '类型', key: 'type' },
        { title: '容量', key: 'capacity' }
      ], rows, r => `<button class="btn-link danger" data-del="${r.id}">删除</button>`)}</div>`;
    document.getElementById('add-loc').onclick = () => openModal({
      title: '新增库位',
      body: `<div class="form-grid">
        <div class="form-item"><label>所属仓库<span class="req">*</span></label><select id="f-wh">${whOptions()}</select></div>
        <div class="form-item"><label>库位编码<span class="req">*</span></label><input id="f-code" placeholder="如 A-03-01"></div>
        <div class="form-item"><label>区域</label><input id="f-zone" placeholder="如 03区"></div>
        <div class="form-item"><label>类型</label><select id="f-type"><option>存储位</option><option>拣货位</option><option>暂存位</option></select></div>
        <div class="form-item"><label>容量</label><input id="f-cap" type="number" value="100"></div></div>`,
      onOk: async () => {
        await api('/api/locations', 'POST', {
          warehouse_id: document.getElementById('f-wh').value,
          code: document.getElementById('f-code').value.trim(),
          zone: document.getElementById('f-zone').value.trim(),
          type: document.getElementById('f-type').value,
          capacity: document.getElementById('f-cap').value
        });
        closeModal(); toast('库位已创建'); VIEWS.master(box);
      }
    });
    body.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
      if (!confirm('确定删除该库位？')) return;
      try { await api('/api/locations/' + b.dataset.del, 'DELETE'); toast('已删除'); VIEWS.master(box); }
      catch (e) { toast(e.message, 'err'); }
    });
  }

  if (tab === 'products') {
    const rows = await api('/api/products');
    body.innerHTML = `<div class="toolbar"><button class="btn btn-primary" id="add-prod">新增商品</button></div>
      <div class="card">${table([
        { title: 'SKU', key: 'sku' }, { title: '商品名称', key: 'name' },
        { title: '分类', key: 'category' }, { title: '单位', key: 'unit' },
        { title: '规格', key: 'spec' }, { title: '单价(元)', render: r => money(r.price) },
        { title: '安全库存', key: 'warn_threshold' }
      ], rows, r => `<button class="btn-link danger" data-del="${r.id}">删除</button>`)}</div>`;
    document.getElementById('add-prod').onclick = () => openModal({
      title: '新增商品 SKU', width: 'wide',
      body: `<div class="form-grid">
        <div class="form-item"><label>SKU 编码<span class="req">*</span></label><input id="f-sku" placeholder="如 SKU10007"></div>
        <div class="form-item"><label>商品名称<span class="req">*</span></label><input id="f-name"></div>
        <div class="form-item"><label>分类</label><input id="f-cat"></div>
        <div class="form-item"><label>单位</label><input id="f-unit" value="件"></div>
        <div class="form-item"><label>规格</label><input id="f-spec"></div>
        <div class="form-item"><label>单价(元)</label><input id="f-price" type="number" value="0"></div>
        <div class="form-item"><label>安全库存</label><input id="f-warn" type="number" value="10"></div></div>`,
      onOk: async () => {
        await api('/api/products', 'POST', {
          sku: document.getElementById('f-sku').value.trim(),
          name: document.getElementById('f-name').value.trim(),
          category: document.getElementById('f-cat').value.trim(),
          unit: document.getElementById('f-unit').value.trim(),
          spec: document.getElementById('f-spec').value.trim(),
          price: document.getElementById('f-price').value,
          warn_threshold: document.getElementById('f-warn').value
        });
        closeModal(); toast('商品已创建'); VIEWS.master(box);
      }
    });
    body.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
      if (!confirm('确定删除该商品？')) return;
      try { await api('/api/products/' + b.dataset.del, 'DELETE'); toast('已删除'); VIEWS.master(box); }
      catch (e) { toast(e.message, 'err'); }
    });
  }

  if (tab === 'suppliers') {
    const rows = await api('/api/suppliers');
    body.innerHTML = `<div class="toolbar"><button class="btn btn-primary" id="add-sup">新增供应商</button></div>
      <div class="card">${table([
        { title: '编码', key: 'code' }, { title: '供应商名称', key: 'name' },
        { title: '联系人', key: 'contact' }, { title: '联系电话', key: 'phone' }
      ], rows)}</div>`;
    document.getElementById('add-sup').onclick = () => openModal({
      title: '新增供应商',
      body: `<div class="form-grid">
        <div class="form-item"><label>供应商编码<span class="req">*</span></label><input id="f-code"></div>
        <div class="form-item"><label>供应商名称<span class="req">*</span></label><input id="f-name"></div>
        <div class="form-item"><label>联系人</label><input id="f-contact"></div>
        <div class="form-item"><label>联系电话</label><input id="f-phone"></div></div>`,
      onOk: async () => {
        await api('/api/suppliers', 'POST', {
          code: document.getElementById('f-code').value.trim(),
          name: document.getElementById('f-name').value.trim(),
          contact: document.getElementById('f-contact').value.trim(),
          phone: document.getElementById('f-phone').value.trim()
        });
        closeModal(); toast('供应商已创建'); VIEWS.master(box);
      }
    });
  }
};

/* ================================================================ 入库管理 */
VIEWS.inbound = async (box) => {
  await loadBase();
  const rows = await api('/api/inbound');
  box.innerHTML = `<div class="toolbar">
      <button class="btn btn-primary" id="add-in">新建入库单</button>
      <span class="hint">流程：创建入库单 → 收货验货（登记实收/合格） → 指定库位上架 → 生成库存与业务事件</span>
    </div>
    <div class="card">${table([
    { title: '入库单号', key: 'order_no' }, { title: '供应商', key: 'supplier_name' },
    { title: '仓库', key: 'warehouse_name' }, { title: '总数量', key: 'total_qty' },
    { title: '状态', render: r => tag(r.status) }, { title: '创建人', key: 'created_by' },
    { title: '创建时间', render: r => fmtTime(r.created_at) }
  ], rows, r => {
    const acts = [];
    if (r.status === '待收货' || r.status === '收货中') acts.push(`<button class="btn-link ok" data-recv="${r.id}">收货验货</button>`);
    if (r.status === '待上架') acts.push(`<button class="btn-link ok" data-put="${r.id}">上架</button>`);
    acts.push(`<button class="btn-link" data-view="${r.id}">明细</button>`);
    return acts.join('');
  })}</div>`;

  document.getElementById('add-in').onclick = () => openCreateInbound(box);
  box.querySelectorAll('[data-view]').forEach(b => b.onclick = () => {
    const r = rows.find(x => x.id == b.dataset.view);
    openModal({
      title: '入库单明细 · ' + r.order_no, width: 'wide',
      body: `<div class="hint" style="margin-bottom:10px">状态：${r.status}　供应商：${esc(r.supplier_name || '')}　仓库：${esc(r.warehouse_name || '')}</div>
        ${table([
        { title: 'SKU', key: 'sku' }, { title: '商品', key: 'product_name' },
        { title: '计划数量', key: 'plan_qty' }, { title: '实收数量', key: 'recv_qty' },
        { title: '合格数量', key: 'qualified_qty' },
        { title: '上架库位', render: x => esc(x.location_code || '-') },
        { title: '状态', render: x => tag(x.status) }
      ], r.items)}`, cancelText: '关闭'
    });
  });
  box.querySelectorAll('[data-recv]').forEach(b => b.onclick = () => {
    const r = rows.find(x => x.id == b.dataset.recv);
    const body = `<table><tbody>${r.items.map((it, i) => `<tr>
        <td style="width:34%">${esc(it.sku)}<br><span class="hint">${esc(it.product_name)}</span></td>
        <td style="width:16%">计划 ${it.plan_qty}</td>
        <td><input type="number" id="recv-${i}" value="${it.plan_qty}" style="width:92px;height:30px;border:1px solid #e5e7eb;border-radius:6px;padding:0 8px" placeholder="实收"></td>
        <td><input type="number" id="qual-${i}" value="${it.plan_qty}" style="width:92px;height:30px;border:1px solid #e5e7eb;border-radius:6px;padding:0 8px" placeholder="合格"></td>
      </tr>`).join('')}</tbody></table>
      <div class="hint" style="margin-top:10px">按实际到货数量填写；合格数量小于实收数量表示存在残次品。</div>`;
    openModal({
      title: '收货验货 · ' + r.order_no, width: 'wide', body,
      okText: '提交验货',
      onOk: async () => {
        const items = r.items.map((it, i) => ({
          id: it.id,
          recv_qty: document.getElementById('recv-' + i).value,
          qualified_qty: document.getElementById('qual-' + i).value
        }));
        const res = await api('/api/inbound/' + r.id + '/receive', 'POST', { items });
        closeModal(); toast('验货完成，合格数量 ' + res.qualified); VIEWS.inbound(box);
      }
    });
  });
  box.querySelectorAll('[data-put]').forEach(b => b.onclick = () => {
    const r = rows.find(x => x.id == b.dataset.put);
    const body = `<table><tbody>${r.items.map((it, i) => `<tr>
        <td style="width:30%">${esc(it.sku)}<br><span class="hint">${esc(it.product_name)}</span></td>
        <td style="width:18%">合格 ${it.qualified_qty}</td>
        <td><select id="loc-${i}" style="width:100%;height:32px;border:1px solid #e5e7eb;border-radius:6px">${locOptions(r.warehouse_id)}</select></td>
        <td><input id="batch-${i}" value="B${new Date().toISOString().slice(0, 10).replace(/-/g, '')}" style="width:110px;height:32px;border:1px solid #e5e7eb;border-radius:6px;padding:0 8px"></td>
      </tr>`).join('')}</tbody></table>`;
    openModal({
      title: '上架 · ' + r.order_no, width: 'wide', body, okText: '确认上架',
      onOk: async () => {
        const items = r.items.map((it, i) => ({
          id: it.id, qualified: it.qualified_qty,
          loc: document.getElementById('loc-' + i), batch: document.getElementById('batch-' + i)
        })).filter(x => x.qualified > 0 && x.loc)
          .map(x => ({ id: x.id, location_id: x.loc.value, batch_no: x.batch.value }));
        if (!items.length) throw new Error('没有可上架的合格品');
        const res = await api('/api/inbound/' + r.id + '/putaway', 'POST', { items });
        closeModal(); toast('上架完成，入库 ' + res.putaway + ' 件，已生成 GoodsInEvent'); VIEWS.inbound(box);
      }
    });
  });
};

function openCreateInbound(box) {
  openModal({
    title: '新建入库单', width: 'wide',
    body: `<div class="form-grid">
      <div class="form-item"><label>供应商<span class="req">*</span></label><select id="i-sup">${cache.suppliers.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></div>
      <div class="form-item"><label>入库仓库<span class="req">*</span></label><select id="i-wh">${whOptions()}</select></div>
      <div class="form-item full"><label>备注</label><input id="i-rem" placeholder="如 10 月常规补货"></div></div>
      <div style="margin-top:16px;display:flex;justify-content:space-between;align-items:center">
        <span class="hint">入库明细</span><button class="btn btn-sm" id="i-add-row">+ 添加一行</button></div>
      <table style="margin-top:8px"><thead><tr><th>商品</th><th style="width:140px">计划数量</th><th style="width:60px"></th></tr></thead>
      <tbody id="i-rows"></tbody></table>`,
    okText: '提交入库单',
    onOk: async () => {
      const items = [...document.querySelectorAll('#i-rows tr')].map(tr => ({
        product_id: tr.querySelector('.p').value, plan_qty: tr.querySelector('.q').value
      })).filter(x => x.plan_qty);
      if (!items.length) throw new Error('请至少添加一条入库明细');
      await api('/api/inbound', 'POST', {
        supplier_id: document.getElementById('i-sup').value,
        warehouse_id: document.getElementById('i-wh').value,
        remark: document.getElementById('i-rem').value,
        items
      });
      closeModal(); toast('入库单已创建'); VIEWS.inbound(box);
    }
  });
  const rows = document.getElementById('i-rows');
  const addRow = () => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><select class="p" style="width:100%;height:32px;border:1px solid #e5e7eb;border-radius:6px">${prodOptions()}</select></td>
      <td><input class="q" type="number" value="10" style="width:100%;height:32px;border:1px solid #e5e7eb;border-radius:6px;padding:0 8px"></td>
      <td><button class="btn-link danger" onclick="this.closest('tr').remove()">删除</button></td>`;
    rows.appendChild(tr);
  };
  addRow();
  document.getElementById('i-add-row').onclick = addRow;
}

/* ================================================================ 库存管理 */
VIEWS.inventory = async (box) => {
  await loadBase();
  const tab = state.tab.inv || 'stock';
  box.innerHTML = `<div class="tabs">
    ${[['stock', '实时库存'], ['warning', '库存预警'], ['check', '盘点管理'], ['moves', '库存流水']]
      .map(([k, n]) => `<div class="tab ${tab === k ? 'active' : ''}" data-tab="${k}">${n}</div>`).join('')}
    </div><div id="inv-body"></div>`;
  box.querySelectorAll('.tab').forEach(el => el.onclick = () => { state.tab.inv = el.dataset.tab; VIEWS.inventory(box); });
  const body = document.getElementById('inv-body');

  if (tab === 'stock') {
    body.innerHTML = `<div class="toolbar">
        <select id="s-wh"><option value="">全部仓库</option>${whOptions()}</select>
        <input id="s-kw" placeholder="搜索 SKU / 商品名 / 库位" style="width:220px">
        <button class="btn" id="s-btn">查询</button></div><div class="card" id="s-list"></div>`;
    const load = async () => {
      const q = new URLSearchParams();
      if (document.getElementById('s-wh').value) q.set('warehouse_id', document.getElementById('s-wh').value);
      if (document.getElementById('s-kw').value) q.set('keyword', document.getElementById('s-kw').value.trim());
      const rows = await api('/api/inventory?' + q.toString());
      document.getElementById('s-list').innerHTML = table([
        { title: '仓库', key: 'warehouse_name' }, { title: '库位', key: 'location_code' },
        { title: 'SKU', key: 'sku' }, { title: '商品名称', key: 'name' },
        { title: '批次', key: 'batch_no' },
        { title: '库存数量', render: r => `<b>${r.qty}</b> ${esc(r.unit)}` },
        { title: '锁定数量', key: 'locked_qty' },
        { title: '可用数量', render: r => r.qty - r.locked_qty },
        { title: '更新时间', render: r => fmtTime(r.updated_at) }
      ], rows);
    };
    document.getElementById('s-btn').onclick = load;
    await load();
  }

  if (tab === 'warning') {
    const rows = await api('/api/inventory/warning');
    body.innerHTML = `<div class="card"><div class="card-head"><h3>库存预警清单</h3>
      <span class="hint">当前库存低于或等于安全库存时自动预警（P2 需求）</span></div>
      ${table([
      { title: 'SKU', key: 'sku' }, { title: '商品名称', key: 'name' },
      { title: '当前库存', render: r => `<b style="color:#b91c1c">${r.qty}</b>` },
      { title: '安全库存', key: 'warn_threshold' },
      { title: '建议补货量', render: r => Math.max(r.warn_threshold * 2 - r.qty, 0) },
      { title: '预警级别', render: r => r.qty === 0 ? tag('缺货') : (r.qty <= r.warn_threshold / 2 ? tag('严重') : tag('一般')) }
    ], rows)}</div>`;
  }

  if (tab === 'check') {
    const rows = await api('/api/checks');
    body.innerHTML = `<div class="toolbar"><button class="btn btn-primary" id="add-check">生成盘点单</button>
      <select id="c-wh">${whOptions()}</select>
      <span class="hint">按所选仓库当前库存生成账面数，录入实盘数后审核调整</span></div>
      <div class="card">${table([
      { title: '盘点单号', key: 'bill_no' }, { title: '仓库', key: 'warehouse_name' },
      { title: '差异条数', key: 'diff_count' }, { title: '状态', render: r => tag(r.status) },
      { title: '创建人', key: 'created_by' }, { title: '创建时间', render: r => fmtTime(r.created_at) }
    ], rows, r => {
      const a = [];
      if (r.status === '待录入') a.push(`<button class="btn-link ok" data-input="${r.id}">录入实盘</button>`);
      if (r.status === '待审核') a.push(`<button class="btn-link ok" data-approve="${r.id}">审核调整</button>`);
      a.push(`<button class="btn-link" data-detail="${r.id}">明细</button>`);
      return a.join('');
    })}</div>`;
    document.getElementById('add-check').onclick = async () => {
      try {
        const res = await api('/api/checks', 'POST', { warehouse_id: document.getElementById('c-wh').value });
        toast('盘点单 ' + res.bill_no + ' 已生成'); VIEWS.inventory(box);
      } catch (e) { toast(e.message, 'err'); }
    };
    box.querySelectorAll('[data-input]').forEach(b => b.onclick = () => {
      const r = rows.find(x => x.id == b.dataset.input);
      const body2 = `<table><tbody>${r.items.map((it, i) => `<tr>
          <td style="width:26%">${esc(it.sku)}<br><span class="hint">${esc(it.product_name)}</span></td>
          <td style="width:18%">${esc(it.location_code)}</td>
          <td style="width:16%">账面 ${it.book_qty}</td>
          <td><input type="number" id="real-${i}" value="${it.book_qty}" style="width:86px;height:30px;border:1px solid #e5e7eb;border-radius:6px;padding:0 8px"></td>
          <td><input id="reason-${i}" placeholder="差异原因" style="width:100%;height:30px;border:1px solid #e5e7eb;border-radius:6px;padding:0 8px"></td>
        </tr>`).join('')}</tbody></table>`;
      openModal({
        title: '录入实盘 · ' + r.bill_no, width: 'wide', body: body2, okText: '提交',
        onOk: async () => {
          const items = r.items.map((it, i) => ({
            id: it.id, real_qty: document.getElementById('real-' + i).value,
            diff_reason: document.getElementById('reason-' + i).value
          }));
          const res = await api('/api/checks/' + r.id + '/input', 'POST', { items });
          closeModal(); toast('已提交，差异 ' + res.diff + ' 条'); VIEWS.inventory(box);
        }
      });
    });
    box.querySelectorAll('[data-approve]').forEach(b => b.onclick = async () => {
      const r = rows.find(x => x.id == b.dataset.approve);
      if (!confirm('审核后将按实盘数调整库存并生成 StockChangeEvent，是否继续？')) return;
      try {
        const res = await api('/api/checks/' + r.id + '/approve', 'POST', {});
        toast('审核完成，调整 ' + res.adjusted + ' 条库存'); VIEWS.inventory(box);
      } catch (e) { toast(e.message, 'err'); }
    });
    box.querySelectorAll('[data-detail]').forEach(b => b.onclick = () => {
      const r = rows.find(x => x.id == b.dataset.detail);
      openModal({
        title: '盘点明细 · ' + r.bill_no, width: 'wide',
        body: table([
          { title: 'SKU', key: 'sku' }, { title: '商品', key: 'product_name' },
          { title: '库位', key: 'location_code' }, { title: '账面数', key: 'book_qty' },
          { title: '实盘数', render: x => x.real_qty === null ? '-' : x.real_qty },
          { title: '差异', render: x => x.real_qty === null ? '-' : (x.real_qty - x.book_qty) },
          { title: '差异原因', render: x => esc(x.diff_reason || '-') }
        ], r.items), cancelText: '关闭'
      });
    });
  }

  if (tab === 'moves') {
    const rows = await api('/api/stock-moves');
    body.innerHTML = `<div class="card"><div class="card-head"><h3>库存流水</h3><span class="hint">入库、出库、盘点调整全过程留痕，可追溯</span></div>
      ${table([
      { title: '时间', render: r => fmtTime(r.created_at) }, { title: '类型', render: r => tag(r.move_type) },
      { title: 'SKU', key: 'sku' }, { title: '商品', key: 'product_name' },
      { title: '库位', key: 'location_code' },
      { title: '数量', render: r => `<b style="color:${r.qty >= 0 ? '#15803d' : '#b91c1c'}">${r.qty > 0 ? '+' : ''}${r.qty}</b>` },
      { title: '关联单据', key: 'ref_no' }, { title: '操作人', key: 'operator' }
    ], rows)}</div>`;
  }
};

/* ================================================================ 拣选作业 */
VIEWS.picking = async (box) => {
  await loadBase();
  const rows = await api('/api/pick-tasks');
  box.innerHTML = `<div class="toolbar">
      <select id="p-status"><option value="">全部状态</option><option>待拣货</option><option>已拣货</option></select>
      <span class="hint">拣货员按库位指引到库位扫描商品条码，确认数量后提交</span></div>
    <div class="card">${table([
    { title: '任务号', key: 'task_no' }, { title: '出库单号', key: 'outbound_no' },
    { title: 'SKU', key: 'sku' }, { title: '商品', key: 'product_name' },
    { title: '库位', key: 'location_code' },
    { title: '应拣数量', key: 'plan_qty' },
    { title: '已拣数量', key: 'picked_qty' },
    { title: '状态', render: r => tag(r.status) },
    { title: '拣货员', render: r => esc(r.picker || '-') }
  ], rows, r => r.status === '待拣货' ? `<button class="btn-link ok" data-pick="${r.id}">扫码确认</button>` : '')}</div>`;
  document.getElementById('p-status').onchange = async (e) => {
    const st = e.target.value;
    const list = st ? await api('/api/pick-tasks?status=' + encodeURIComponent(st)) : await api('/api/pick-tasks');
    const card = box.querySelector('.card');
    card.innerHTML = table([
      { title: '任务号', key: 'task_no' }, { title: '出库单号', key: 'outbound_no' },
      { title: 'SKU', key: 'sku' }, { title: '商品', key: 'product_name' },
      { title: '库位', key: 'location_code' }, { title: '应拣数量', key: 'plan_qty' },
      { title: '已拣数量', key: 'picked_qty' }, { title: '状态', render: x => tag(x.status) },
      { title: '拣货员', render: x => esc(x.picker || '-') }
    ], list, x => x.status === '待拣货' ? `<button class="btn-link ok" data-pick="${x.id}">扫码确认</button>` : '');
    bindPick(card, list);
  };
  bindPick(box, rows);
};

function bindPick(scope, rows) {
  scope.querySelectorAll('[data-pick]').forEach(b => b.onclick = () => {
    const r = rows.find(x => x.id == b.dataset.pick);
    openModal({
      title: '拣货确认 · ' + r.task_no,
      body: `<div class="form-grid">
        <div class="form-item full"><label>库位指引</label><input value="${esc(r.location_code)}（${esc(r.product_name)}）" disabled></div>
        <div class="form-item"><label>应拣数量</label><input value="${r.plan_qty}" disabled></div>
        <div class="form-item"><label>实拣数量<span class="req">*</span></label><input id="pk-qty" type="number" value="${r.plan_qty}"></div>
        <div class="form-item full"><label>拣货员</label><input id="pk-who" value="${esc(ME.name)}"></div></div>`,
      okText: '确认拣货',
      onOk: async () => {
        await api('/api/pick-tasks/' + r.id + '/confirm', 'POST', {
          picked_qty: document.getElementById('pk-qty').value,
          picker: document.getElementById('pk-who').value
        });
        closeModal(); toast('拣货完成'); VIEWS.picking(document.getElementById('view'));
      }
    });
  });
}

/* ================================================================ 出库与物流 */
VIEWS.outbound = async (box) => {
  await loadBase();
  const tab = state.tab.out || 'orders';
  box.innerHTML = `<div class="tabs">
    ${[['orders', '出库单'], ['waybills', '运单与物流轨迹']]
      .map(([k, n]) => `<div class="tab ${tab === k ? 'active' : ''}" data-tab="${k}">${n}</div>`).join('')}
    </div><div id="out-body"></div>`;
  box.querySelectorAll('.tab').forEach(el => el.onclick = () => { state.tab.out = el.dataset.tab; VIEWS.outbound(box); });
  const body = document.getElementById('out-body');

  if (tab === 'orders') {
    const rows = await api('/api/outbound');
    body.innerHTML = `<div class="toolbar"><button class="btn btn-primary" id="add-out">新建出库单</button>
      <span class="hint">流程：创建出库单（自动锁定分配库存并生成拣货任务） → 拣货 → 复核 → 确认出库 → 生成运单并推送物流平台</span></div>
      <div class="card">${table([
      { title: '出库单号', key: 'order_no' }, { title: '客户', key: 'customer' },
      { title: '仓库', key: 'warehouse_name' }, { title: '数量', key: 'total_qty' },
      { title: '优先级', render: r => r.priority === '加急' ? tag('加急') : esc(r.priority) },
      { title: '状态', render: r => tag(r.status) },
      { title: '运单号', render: r => esc(r.waybill ? r.waybill.waybill_no : '-') },
      { title: '创建时间', render: r => fmtTime(r.created_at) }
    ], rows, r => {
      const a = [`<button class="btn-link" data-detail="${r.id}">明细</button>`];
      if (r.status === '待复核') a.push(`<button class="btn-link ok" data-review="${r.id}">复核</button>`);
      if (r.status === '待出库') a.push(`<button class="btn-link ok" data-ship="${r.id}">确认出库</button>`);
      return a.join('');
    })}</div>`;
    document.getElementById('add-out').onclick = () => openCreateOutbound(box);

    body.querySelectorAll('[data-detail]').forEach(b => b.onclick = () => {
      const r = rows.find(x => x.id == b.dataset.detail);
      openModal({
        title: '出库单明细 · ' + r.order_no, width: 'wide',
        body: `<div class="hint" style="margin-bottom:10px">客户：${esc(r.customer || '-')}　仓库：${esc(r.warehouse_name)}　状态：${r.status}</div>
          ${table([
          { title: 'SKU', key: 'sku' }, { title: '商品', key: 'product_name' },
          { title: '计划数量', key: 'plan_qty' }, { title: '已拣数量', key: 'picked_qty' },
          { title: '库位', render: x => esc(x.location_code || '-') }
        ], r.items)}`, cancelText: '关闭'
      });
    });
    body.querySelectorAll('[data-review]').forEach(b => b.onclick = async () => {
      const r = rows.find(x => x.id == b.dataset.review);
      try { await api('/api/outbound/' + r.id + '/review', 'POST', {}); toast('复核通过，可确认出库'); VIEWS.outbound(box); }
      catch (e) { toast(e.message, 'err'); }
    });
    body.querySelectorAll('[data-ship]').forEach(b => b.onclick = () => {
      const r = rows.find(x => x.id == b.dataset.ship);
      openModal({
        title: '确认出库并推送物流 · ' + r.order_no,
        body: `<div class="form-grid">
          <div class="form-item"><label>承运商<span class="req">*</span></label>
            <select id="sh-carrier"><option>顺丰速运</option><option>京东物流</option><option>中通快递</option><option>德邦物流(模拟异常)</option></select></div>
          <div class="form-item"><label>目的地</label><input id="sh-dest" value="${esc(r.customer || '')}"></div></div>
          <div class="hint" style="margin-top:10px">确认后扣减库存、生成运单并自动调用承运平台接口推送；选择“模拟异常”可演示推送失败与重试。</div>`,
        okText: '确认出库',
        onOk: async () => {
          const res = await api('/api/outbound/' + r.id + '/ship', 'POST', {
            carrier: document.getElementById('sh-carrier').value,
            dest: document.getElementById('sh-dest').value
          });
          closeModal();
          toast(res.push.ok ? '出库完成，运单 ' + res.waybill_no + ' 推送成功' : '出库完成，但运单推送失败：' + res.push.msg, res.push.ok ? 'ok' : 'err');
          VIEWS.outbound(box);
        }
      });
    });
  }

  if (tab === 'waybills') {
    const rows = await api('/api/waybills');
    body.innerHTML = `<div class="card"><div class="card-head"><h3>运单列表</h3>
        <span class="hint">推送失败可重试；“同步轨迹”模拟向承运平台查询最新节点</span></div>
      ${table([
      { title: '运单号', key: 'waybill_no' }, { title: '出库单号', key: 'outbound_no' },
      { title: '承运商', key: 'carrier' }, { title: '目的地', key: 'dest' },
      { title: '状态', render: r => tag(r.status) },
      { title: '推送次数', key: 'push_attempts' },
      { title: '推送时间', render: r => fmtTime(r.pushed_at) }
    ], rows, r => {
      const a = [`<button class="btn-link" data-trace="${r.id}">轨迹</button>`];
      if (r.status === '推送失败') a.push(`<button class="btn-link ok" data-retry="${r.id}">重试推送</button>`);
      if (r.status === '已推送') a.push(`<button class="btn-link ok" data-sync="${r.id}">同步轨迹</button>`);
      return a.join('');
    })}</div>`;
    body.querySelectorAll('[data-trace]').forEach(b => b.onclick = async () => {
      const d = await api('/api/waybills/' + b.dataset.trace + '/trace');
      openModal({
        title: '物流轨迹 · ' + d.waybill.waybill_no, width: 'wide',
        body: `<div class="hint" style="margin-bottom:12px">${esc(d.waybill.carrier)} → ${esc(d.waybill.dest || '')}　当前状态：${d.waybill.status}</div>
          ${table([{ title: '时间', render: r => fmtTime(r.time) }, { title: '节点', render: r => tag(r.node) },
        { title: '描述', key: 'description' }], d.traces)}`, cancelText: '关闭'
      });
    });
    body.querySelectorAll('[data-retry]').forEach(b => b.onclick = async () => {
      try {
        const res = await api('/api/waybills/' + b.dataset.retry + '/push', 'POST', {});
        toast(res.ok ? res.msg : res.msg, res.ok ? 'ok' : 'err'); VIEWS.outbound(box);
      } catch (e) { toast(e.message, 'err'); }
    });
    body.querySelectorAll('[data-sync]').forEach(b => b.onclick = async () => {
      try {
        const res = await api('/api/waybills/' + b.dataset.sync + '/sync', 'POST', {});
        toast(res.msg || ('已同步节点：' + res.node)); VIEWS.outbound(box);
      } catch (e) { toast(e.message, 'err'); }
    });
  }
};

function openCreateOutbound(box) {
  openModal({
    title: '新建出库单', width: 'wide',
    body: `<div class="form-grid">
      <div class="form-item"><label>客户名称<span class="req">*</span></label><input id="o-cus" placeholder="如 北京华联商贸"></div>
      <div class="form-item"><label>出库仓库<span class="req">*</span></label><select id="o-wh">${whOptions()}</select></div>
      <div class="form-item"><label>优先级</label><select id="o-pri"><option>普通</option><option>加急</option></select></div>
      <div class="form-item"><label>备注</label><input id="o-rem"></div></div>
      <div style="margin-top:16px;display:flex;justify-content:space-between;align-items:center">
        <span class="hint">出库明细（提交后自动锁定库存并生成拣货任务）</span>
        <button class="btn btn-sm" id="o-add-row">+ 添加一行</button></div>
      <table style="margin-top:8px"><thead><tr><th>商品</th><th style="width:140px">出库数量</th><th style="width:60px"></th></tr></thead>
      <tbody id="o-rows"></tbody></table>`,
    okText: '提交出库单',
    onOk: async () => {
      const items = [...document.querySelectorAll('#o-rows tr')].map(tr => ({
        product_id: tr.querySelector('.p').value, plan_qty: tr.querySelector('.q').value
      })).filter(x => x.plan_qty);
      if (!items.length) throw new Error('请至少添加一条出库明细');
      await api('/api/outbound', 'POST', {
        customer: document.getElementById('o-cus').value.trim(),
        warehouse_id: document.getElementById('o-wh').value,
        priority: document.getElementById('o-pri').value,
        remark: document.getElementById('o-rem').value,
        items
      });
      closeModal(); toast('出库单已创建，拣货任务已生成'); VIEWS.outbound(box);
    }
  });
  const rows = document.getElementById('o-rows');
  const addRow = () => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><select class="p" style="width:100%;height:32px;border:1px solid #e5e7eb;border-radius:6px">${prodOptions()}</select></td>
      <td><input class="q" type="number" value="5" style="width:100%;height:32px;border:1px solid #e5e7eb;border-radius:6px;padding:0 8px"></td>
      <td><button class="btn-link danger" onclick="this.closest('tr').remove()">删除</button></td>`;
    rows.appendChild(tr);
  };
  addRow();
  document.getElementById('o-add-row').onclick = addRow;
}

/* ================================================================ 系统管理 */
VIEWS.system = async (box) => {
  const tab = state.tab.sys || 'users';
  box.innerHTML = `<div class="tabs">
    ${[['users', '用户管理'], ['roles', '角色权限'], ['events', '业务事件'], ['logs', '操作日志']]
      .map(([k, n]) => `<div class="tab ${tab === k ? 'active' : ''}" data-tab="${k}">${n}</div>`).join('')}
    </div><div id="sys-body"></div>`;
  box.querySelectorAll('.tab').forEach(el => el.onclick = () => { state.tab.sys = el.dataset.tab; VIEWS.system(box); });
  const body = document.getElementById('sys-body');

  if (tab === 'users') {
    const [rows, roles] = await Promise.all([api('/api/users'), api('/api/roles')]);
    cache.roles = roles;
    body.innerHTML = `<div class="toolbar"><button class="btn btn-primary" id="add-user">新增用户</button>
      <span class="hint">基于 RBAC 模型：用户 → 角色 → 权限集合，接口按权限校验</span></div>
      <div class="card">${table([
      { title: '账号', key: 'username' }, { title: '姓名', key: 'name' },
      { title: '角色', key: 'role_name' }, { title: '手机号', key: 'phone' },
      { title: '状态', render: r => r.status === 1 ? tag('正常') : tag('已停用') },
      { title: '创建时间', render: r => fmtTime(r.created_at) }
    ], rows, r => `<button class="btn-link danger" data-del="${r.id}">删除</button>`)}</div>`;
    document.getElementById('add-user').onclick = () => openModal({
      title: '新增用户',
      body: `<div class="form-grid">
        <div class="form-item"><label>账号<span class="req">*</span></label><input id="u-name" placeholder="登录账号"></div>
        <div class="form-item"><label>密码<span class="req">*</span></label><input id="u-pwd" type="password" value="123456"></div>
        <div class="form-item"><label>姓名<span class="req">*</span></label><input id="u-real"></div>
        <div class="form-item"><label>角色<span class="req">*</span></label><select id="u-role">${roles.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join('')}</select></div>
        <div class="form-item full"><label>手机号</label><input id="u-phone"></div></div>`,
      onOk: async () => {
        await api('/api/users', 'POST', {
          username: document.getElementById('u-name').value.trim(),
          password: document.getElementById('u-pwd').value.trim(),
          name: document.getElementById('u-real').value.trim(),
          role_id: document.getElementById('u-role').value,
          phone: document.getElementById('u-phone').value.trim()
        });
        closeModal(); toast('用户已创建'); VIEWS.system(box);
      }
    });
    body.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
      if (!confirm('确定删除该用户？')) return;
      try { await api('/api/users/' + b.dataset.del, 'DELETE'); toast('已删除'); VIEWS.system(box); }
      catch (e) { toast(e.message, 'err'); }
    });
  }

  if (tab === 'roles') {
    const roles = await api('/api/roles'); cache.roles = roles;
    const PERMS = [['dashboard', '工作台'], ['master', '基础数据'], ['inbound', '入库管理'],
    ['inventory', '库存管理'], ['picking', '拣选作业'], ['outbound', '出库与物流'], ['system', '系统管理']];
    body.innerHTML = `<div class="card"><div class="card-head"><h3>角色权限配置</h3>
        <span class="hint">勾选后保存，权限即时生效（接口层同步校验）</span></div>
      ${roles.map(r => `<div style="padding:12px 0;border-bottom:1px dashed #eef1f4">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
          <b>${esc(r.name)}</b><span class="tag">${esc(r.code)}</span>
          <button class="btn btn-sm btn-primary" data-save="${r.id}">保存权限</button></div>
        <div style="display:flex;flex-wrap:wrap;gap:8px 18px">
          ${PERMS.map(([k, n]) => `<label style="font-size:13px;display:flex;align-items:center;gap:6px">
            <input type="checkbox" data-role="${r.id}" value="${k}" ${r.permissions.includes(k) ? 'checked' : ''}>${n}</label>`).join('')}
        </div></div>`).join('')}</div>`;
    body.querySelectorAll('[data-save]').forEach(btn => btn.onclick = async () => {
      const rid = btn.dataset.save;
      const perms = [...body.querySelectorAll(`[data-role="${rid}"]:checked`)].map(x => x.value);
      try { await api('/api/roles/' + rid, 'PUT', { permissions: perms }); toast('权限已保存'); }
      catch (e) { toast(e.message, 'err'); }
    });
  }

  if (tab === 'events') {
    const rows = await api('/api/events');
    body.innerHTML = `<div class="card"><div class="card-head"><h3>业务事件日志</h3>
        <span class="hint">事件驱动架构：业务动作发布事件，由事件总线消费并持久化</span></div>
      ${table([
      { title: '事件 ID', key: 'id' },
      { title: '事件类型', render: r => `<span class="tag teal">${esc(r.event_type)}</span>` },
      { title: '聚合根', key: 'aggregate_id' },
      { title: '事件内容', render: r => `<span style="font-size:12px;color:#4b5563">${esc(r.payload)}</span>` },
      { title: '状态', key: 'status' },
      { title: '时间', render: r => fmtTime(r.created_at) }
    ], rows)}</div>`;
  }

  if (tab === 'logs') {
    const rows = await api('/api/logs');
    body.innerHTML = `<div class="card"><div class="card-head"><h3>操作日志</h3><span class="hint">全链路操作留痕，支持问题追溯</span></div>
      ${table([
      { title: '时间', render: r => fmtTime(r.created_at) }, { title: '操作人', key: 'username' },
      { title: '操作', key: 'action' }, { title: '对象', key: 'target' }, { title: '详情', key: 'detail' }
    ], rows)}</div>`;
  }
};

/* ---------------- 启动 ---------------- */
(async function boot() {
  if (TOKEN) {
    try { ME = await api('/api/me'); enterApp(); return; } catch (e) { /* token 失效 */ }
  }
  document.getElementById('login-page').classList.remove('hidden');
})();
