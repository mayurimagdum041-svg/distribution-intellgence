/**
 * OptiStock AI — simple.js
 * Fixed field names matching actual Flask API output.
 * Includes Google-style Leaflet map with Maharashtra shipment locations.
 */

/* ══════════════════════════════════════
   USER ROLES & AUTHENTICATION
══════════════════════════════════════ */
const USER_ROLES = {
  admin: {
    key: 'admin',
    name: 'System Administrator',
    badge: '👑 Administrator',
    avatar: 'AD',
    color: '#2563eb',
    allowedSections: ['overview', 'distribution', 'inventory', 'forecast', 'whatif', 'map'],
    defaultSection: 'overview',
    bannerIcon: '👑',
    bannerTitle: 'Logged in as Administrator (Full Access)',
    bannerDesc: 'Full executive control: global network KPIs, SciPy HiGHS MILP solver, What-If simulation sandbox, and all reports.'
  },
  warehouse: {
    key: 'warehouse',
    name: 'Pune Regional DC Head',
    badge: '🏭 Warehouse Manager',
    avatar: 'WH',
    color: '#d97706',
    allowedSections: ['inventory', 'distribution', 'map'],
    defaultSection: 'inventory',
    defaultSubTab: 'warehouses',
    bannerIcon: '🏭',
    bannerTitle: 'Logged in as Warehouse Manager (Pune Hub)',
    bannerDesc: 'Monitoring batch shelf-life (FEFO radar), cold-chain pallet storage, warehouse valuation, and outbound manifests.'
  },
  retail: {
    key: 'retail',
    name: 'Store Operations Head',
    badge: '🏪 Retail Store Manager',
    avatar: 'RT',
    color: '#16a34a',
    allowedSections: ['inventory', 'distribution', 'forecast'],
    defaultSection: 'inventory',
    defaultSubTab: 'stores',
    bannerIcon: '🏪',
    bannerTitle: 'Logged in as Retail Store Manager',
    bannerDesc: 'Tracking store on-hand stock, Days of Cover, Reorder Points (ROP), stockout prevention, and ML demand forecasts.'
  },
  delivery: {
    key: 'delivery',
    name: 'Maharashtra Corridor Fleet',
    badge: '🚚 Delivery Fleet',
    avatar: 'DL',
    color: '#7c3aed',
    allowedSections: ['map', 'distribution'],
    defaultSection: 'map',
    bannerIcon: '🚚',
    bannerTitle: 'Logged in as Delivery Partner & Driver Fleet',
    bannerDesc: 'Live GPS dispatch route navigation, driver assignments, and delivery checkpoints for Pune, Satara, Kolhapur, Sangli, and Karad.'
  }
};

/* ══════════════════════════════════════
   STATE
══════════════════════════════════════ */
const state = {
  currentUser: 'admin',
  currentSection: 'overview',
  horizon: 3,
  summary: null,
  plan: null,
  storeInventory: null,
  whInventory: null,
  meta: null,
  planRows: [],
  storeRows: [],
  whRows: [],
  overviewChart: null,
  forecastChart: null,
  leafletMap: null,
};

/* ══════════════════════════════════════
   LIVE DELIVERY STOPS (Pune, Satara, Kolhapur, Sangli, Karad)
══════════════════════════════════════ */
let liveDeliveryStops = {
  "LOC-PUNE":     { city: "Pune",     status: "In Transit",        eta: "45 mins",        driver: "Rajesh Shinde", vehicle: "MH-12-Q-4021" },
  "LOC-SATARA":   { city: "Satara",   status: "Dispatched",        eta: "2 hrs 10 mins",  driver: "Sachin Kadam",  vehicle: "MH-11-V-8812" },
  "LOC-KOLHAPUR": { city: "Kolhapur", status: "Out for Delivery",  eta: "3 hrs 30 mins",  driver: "Amit Patil",    vehicle: "MH-09-AA-1004" },
  "LOC-SANGLI":   { city: "Sangli",   status: "In Transit",        eta: "3 hrs 45 mins",  driver: "Sunil More",    vehicle: "MH-10-CX-9421" },
  "LOC-KARAD":    { city: "Karad",    status: "Scheduled",         eta: "2 hrs 40 mins",  driver: "Nitin Sawant",  vehicle: "MH-50-B-3100" }
};

/* ══════════════════════════════════════
   NEW DELIVERY LOCATIONS — Maharashtra
   Pune, Satara, Kolhapur, Sangli, Karad
══════════════════════════════════════ */
const NEW_LOCATIONS = [
  { id: 'LOC-PUNE',     name: 'Pune Distribution Point',     city: 'Pune',     lat: 18.5204, lng: 73.8567, type: 'New Delivery' },
  { id: 'LOC-SATARA',   name: 'Satara Retail Hub',           city: 'Satara',   lat: 17.6805, lng: 74.0183, type: 'New Delivery' },
  { id: 'LOC-KOLHAPUR', name: 'Kolhapur Agro Centre',        city: 'Kolhapur', lat: 16.7050, lng: 74.2433, type: 'New Delivery' },
  { id: 'LOC-SANGLI',   name: 'Sangli Distribution Centre',  city: 'Sangli',   lat: 16.8524, lng: 74.5815, type: 'New Delivery' },
  { id: 'LOC-KARAD',    name: 'Karad Logistics Point',       city: 'Karad',    lat: 17.2882, lng: 74.1836, type: 'New Delivery' },
];

/* ══════════════════════════════════════
   ROLE SWITCHING & ACCESS CONTROL
══════════════════════════════════════ */
function switchUserRole(roleKey) {
  const role = USER_ROLES[roleKey];
  if (!role) return;

  state.currentUser = roleKey;
  try {
    localStorage.setItem('optistock_user_role', roleKey);
  } catch(e) {}

  updateRoleUI(role);

  // If the current section is not allowed in this role, navigate to default
  if (!role.allowedSections.includes(state.currentSection)) {
    const defaultNav = document.querySelector(`.nav-link[data-nav="${role.defaultSection}"]`);
    navigate(role.defaultSection, defaultNav);
  } else {
    // Re-highlight active nav link
    const currentNav = document.querySelector(`.nav-link[data-nav="${state.currentSection}"]`);
    if (currentNav) {
      document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
      currentNav.classList.add('active');
    }
  }

  // Handle specific sub-tab landing preferences
  if (role.defaultSubTab && state.currentSection === 'inventory') {
    switchSubTab(role.defaultSubTab);
  }

  // If map section is active, re-render fleet stops
  if (state.currentSection === 'map') {
    renderFleetStops();
  }
}

function updateRoleUI(role) {
  // Update Topbar Chips
  document.querySelectorAll('.role-chip').forEach(btn => btn.classList.remove('active'));
  const activeChip = document.getElementById(`btn-role-${role.key}`);
  if (activeChip) activeChip.classList.add('active');

  // Update Sidebar Profile Card
  const avatarEl = document.getElementById('sidebar-user-avatar');
  const nameEl   = document.getElementById('sidebar-user-name');
  const badgeEl  = document.getElementById('sidebar-user-badge');

  if (avatarEl) {
    avatarEl.textContent = role.avatar;
    avatarEl.style.background = role.color;
  }
  if (nameEl) nameEl.textContent = role.name;
  if (badgeEl) badgeEl.textContent = role.badge;

  // Filter Sidebar Nav Links according to permissions
  document.querySelectorAll('.nav-link').forEach(link => {
    const navKey = link.getAttribute('data-nav');
    if (!navKey) return;
    if (role.allowedSections.includes(navKey)) {
      link.style.display = 'flex';
    } else {
      link.style.display = 'none';
    }
  });

  // Update Role Notification Banner
  const banner = document.getElementById('role-welcome-banner');
  const iconEl = document.getElementById('rwb-icon');
  const titleEl= document.getElementById('rwb-title');
  const descEl = document.getElementById('rwb-desc');

  if (banner) {
    banner.style.borderLeftColor = role.color;
  }
  if (iconEl) iconEl.textContent = role.bannerIcon;
  if (titleEl) titleEl.textContent = role.bannerTitle;
  if (descEl) descEl.textContent = role.bannerDesc;
}

function openRoleModal() {
  const modal = document.getElementById('role-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeRoleModal() {
  const modal = document.getElementById('role-modal');
  if (modal) modal.classList.add('hidden');
}

function selectRoleAndClose(roleKey) {
  switchUserRole(roleKey);
  closeRoleModal();
}

/* ══════════════════════════════════════
   NAVIGATION
══════════════════════════════════════ */
const SECTION_META = {
  overview:     { title: 'Overview',      subtitle: 'Key performance indicators at a glance' },
  distribution: { title: 'Distribution',  subtitle: 'AI-optimised shipment plan for the selected horizon' },
  inventory:    { title: 'Inventory',     subtitle: 'Store health and warehouse batch status' },
  forecast:     { title: 'Forecast',      subtitle: 'ML-driven demand forecast by store and product' },
  whatif:       { title: 'What-If',       subtitle: 'Run scenario simulations with custom shocks' },
  map:          { title: 'Shipment Map',  subtitle: 'Live route map — Warehouses to delivery locations across Maharashtra' },
};

function navigate(section, linkEl) {
  if (window.event) window.event.preventDefault();

  // If user role does not allow this section, block navigation
  const currentRole = USER_ROLES[state.currentUser];
  if (currentRole && !currentRole.allowedSections.includes(section)) {
    section = currentRole.defaultSection;
    linkEl = document.querySelector(`.nav-link[data-nav="${section}"]`);
  }

  document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
  if (linkEl) {
    linkEl.classList.add('active');
  } else {
    const foundLink = document.querySelector(`.nav-link[data-nav="${section}"]`);
    if (foundLink) foundLink.classList.add('active');
  }

  document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
  const target = document.getElementById('section-' + section);
  if (target) target.classList.add('active');

  const meta = SECTION_META[section] || {};
  document.getElementById('page-title').textContent = meta.title || section;
  document.getElementById('page-subtitle').textContent = meta.subtitle || '';
  state.currentSection = section;

  lazyLoad(section);
}

function onHorizonChange() {
  const val = parseInt(document.getElementById('horizon-select').value, 10);
  state.horizon = isNaN(val) ? 3 : val;
  state.summary = null;
  state.plan = null;
  state.storeInventory = null;
  lazyLoad(state.currentSection);
}

function refreshCurrentSection() {
  state.summary = null;
  state.plan = null;
  state.storeInventory = null;
  state.whInventory = null;
  lazyLoad(state.currentSection);
}

function lazyLoad(section) {
  switch (section) {
    case 'overview':     if (!state.summary)       loadSummary();      break;
    case 'distribution': if (!state.plan)           loadPlan();         break;
    case 'inventory':    if (!state.storeInventory) loadInventory();    break;
    case 'forecast':     if (!state.meta)           loadForecastMeta(); break;
    case 'whatif':       if (!state.meta)           loadWhatIfMeta();   break;
    case 'map':          initMap();                                      break;
  }
}

/* ══════════════════════════════════════
   FORMATTING HELPERS
══════════════════════════════════════ */
function fmtINR(val) {
  if (val == null || isNaN(val)) return '—';
  val = Number(val);
  if (val >= 1e7) return '₹' + (val / 1e7).toFixed(2) + ' Cr';
  if (val >= 1e5) return '₹' + (val / 1e5).toFixed(2) + ' L';
  if (val >= 1e3) return '₹' + (val / 1e3).toFixed(1) + 'K';
  return '₹' + val.toFixed(0);
}

function fmtNum(val) {
  if (val == null || isNaN(val)) return '—';
  return Number(val).toLocaleString('en-IN');
}

function fmtPct(val) {
  if (val == null || isNaN(val)) return '—';
  return Number(val).toFixed(1) + '%';
}

function chipClass(status) {
  if (!status) return '';
  const s = status.toLowerCase();
  if (s.includes('critical') || s.includes('urgent')) return 'chip chip-critical';
  if (s.includes('warning') || s.includes('expiring')) return 'chip chip-warning';
  if (s.includes('healthy')) return 'chip chip-healthy';
  return 'chip';
}

function truncate(text, len = 60) {
  if (!text) return '—';
  const t = String(text);
  return t.length > len ? `<span title="${t.replace(/"/g,"'")}">${t.slice(0, len)}…</span>` : t;
}

/* ══════════════════════════════════════
   API HELPERS
══════════════════════════════════════ */
async function apiFetch(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`);
  return res.json();
}

function tableError(tbodyId, colSpan, msg) {
  const el = document.getElementById(tbodyId);
  if (el) el.innerHTML = `<tr><td colspan="${colSpan}" class="loading-row" style="color:#dc2626">⚠️ ${msg}</td></tr>`;
}

/* ══════════════════════════════════════
   SECTION: OVERVIEW
══════════════════════════════════════ */
async function loadSummary() {
  try {
    const data = await apiFetch(`/api/summary?days=${state.horizon}`);
    state.summary = data;
    renderKPICards(data);
    renderBenefitBanner(data);
    renderOverviewChart(data);
  } catch (err) {
    document.getElementById('kpi-grid').innerHTML =
      `<div style="color:var(--danger);padding:1rem;grid-column:1/-1">⚠️ Failed to load KPIs: ${err.message}</div>`;
    console.error('[loadSummary]', err);
  }
}

function renderKPICards(d) {
  const cards = [
    { icon: '📦', label: 'Total Stock Units',    value: fmtNum(d.total_inventory_units), accent: 'kpi-primary' },
    { icon: '💰', label: 'Stock Value',           value: fmtINR(d.total_inventory_value), accent: 'kpi-primary' },
    { icon: '🚨', label: 'Critical Stores',       value: fmtNum(d.critical_stockouts),
      valueClass: d.critical_stockouts > 0 ? 'value-danger' : '',
      accent: d.critical_stockouts > 0 ? 'kpi-danger' : '' },
    { icon: '⚠️', label: 'At-Risk Stores',        value: fmtNum(d.warning_stockouts),
      valueClass: d.warning_stockouts > 0 ? 'value-warning' : '',
      accent: d.warning_stockouts > 0 ? 'kpi-warning' : '' },
    { icon: '🚚', label: 'Shipments Planned',     value: fmtNum(d.shipment_count),       accent: 'kpi-primary' },
    { icon: '📈', label: 'Fulfillment Rate (AI)', value: fmtPct(d.fulfillment_rate_ai),  valueClass: 'value-success', accent: 'kpi-success' },
    { icon: '💸', label: 'Transport Savings',     value: fmtINR(d.transport_savings),    valueClass: 'value-success', accent: 'kpi-success' },
    { icon: '🗑️', label: 'Spoilage Prevented',   value: fmtINR(d.spoilage_averted_savings), valueClass: 'value-success', accent: 'kpi-success' },
  ];
  const grid = document.getElementById('kpi-grid');
  grid.innerHTML = cards.map(c => `
    <div class="kpi-card ${c.accent || ''}">
      <div class="kpi-icon">${c.icon}</div>
      <div class="kpi-body">
        <div class="kpi-value ${c.valueClass || ''}">${c.value}</div>
        <div class="kpi-label">${c.label}</div>
      </div>
    </div>
  `).join('');
}

function renderBenefitBanner(d) {
  const banner = document.getElementById('benefit-banner');
  const val    = document.getElementById('benefit-value');
  if (d.total_economic_benefit != null) {
    val.textContent = fmtINR(d.total_economic_benefit);
    banner.classList.remove('hidden');
  }
}

function renderOverviewChart(d) {
  const ctx = document.getElementById('overview-chart').getContext('2d');
  if (state.overviewChart) { state.overviewChart.destroy(); state.overviewChart = null; }
  state.overviewChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Fulfillment Rate (%)', 'Transport Cost (₹K)', 'Unmet Units'],
      datasets: [
        {
          label: 'AI Optimised',
          data: [
            parseFloat(d.fulfillment_rate_ai) || 0,
            parseFloat((d.total_transport_cost / 1000).toFixed(2)) || 0,
            parseInt(d.total_unmet_units) || 0,
          ],
          backgroundColor: 'rgba(37,99,235,0.85)',
          borderRadius: 6,
        },
        {
          label: 'Baseline (No AI)',
          data: [
            parseFloat(d.fulfillment_rate_baseline) || 0,
            parseFloat((d.baseline_transport_cost / 1000).toFixed(2)) || 0,
            (parseInt(d.total_unmet_units) || 0) + (parseInt(d.stockouts_prevented_units) || 0),
          ],
          backgroundColor: 'rgba(100,116,139,0.5)',
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { family: 'Inter' } } },
        y: { beginAtZero: true, ticks: { font: { family: 'Inter' } }, grid: { color: '#f1f5f9' } },
      },
    },
  });
}

/* ══════════════════════════════════════
   SECTION: DISTRIBUTION PLAN
   Real API field names:
     product, warehouse, store, city,
     quantity, expiry_days, transport_cost,
     unit_transport_cost, reason, category,
     batch_id, storage
══════════════════════════════════════ */
async function loadPlan() {
  document.getElementById('plan-tbody').innerHTML =
    '<tr><td colspan="7" class="loading-row">Loading shipment plan…</td></tr>';
  document.getElementById('unmet-tbody').innerHTML =
    '<tr><td colspan="4" class="loading-row">Loading unmet demand…</td></tr>';

  try {
    const data = await apiFetch(`/api/plan?days=${state.horizon}`);
    state.plan = data;

    // Populate category filter
    const categories = [...new Set((data.shipments || []).map(s => s.category).filter(Boolean))].sort();
    const catSel = document.getElementById('plan-category');
    catSel.innerHTML = '<option value="">All Categories</option>' +
      categories.map(c => `<option value="${c}">${c}</option>`).join('');

    state.planRows = data.shipments || [];
    renderPlanTable(state.planRows);
    renderUnmetTable(data.unmet_demand || []);

    const count = (data.shipments || []).length;
    document.getElementById('plan-count').textContent =
      `${count} shipments · ${fmtNum(data.units_shipped)} units · ${fmtINR(data.total_transport_cost)} freight`;
  } catch (err) {
    tableError('plan-tbody', 7, err.message);
    tableError('unmet-tbody', 4, err.message);
    console.error('[loadPlan]', err);
  }
}

function renderPlanTable(rows) {
  const tbody = document.getElementById('plan-tbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading-row">No shipments found.</td></tr>';
    return;
  }
  // Real field names from API: product, warehouse, store, quantity, expiry_days, transport_cost, reason
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td><strong>${r.product || '—'}</strong><br><small class="text-muted">${r.category || ''}</small></td>
      <td>${r.warehouse || '—'}<br><small class="text-muted">${r.warehouse_id || ''}</small></td>
      <td>${r.store || '—'}<br><small class="text-muted">${r.city || ''}</small></td>
      <td><strong>${fmtNum(r.quantity)}</strong></td>
      <td>${r.expiry_days != null ? r.expiry_days + ' d' : '—'}</td>
      <td style="color:var(--primary);font-weight:600">${fmtINR(r.transport_cost)}</td>
      <td class="text-muted" style="font-size:.78rem;max-width:260px;white-space:normal;line-height:1.4">${truncate(r.reason, 80)}</td>
    </tr>
  `).join('');
}

function renderUnmetTable(rows) {
  const tbody = document.getElementById('unmet-tbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="loading-row" style="color:var(--success)">✅ All demand fulfilled!</td></tr>';
    document.getElementById('unmet-count').textContent = 'No unmet demand';
    return;
  }
  document.getElementById('unmet-count').textContent = `${rows.length} store-product pairs with unmet demand`;
  // Real field names: product, store, city, unmet_units (or unmet_quantity)
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.product || r.product_name || '—'}</td>
      <td>${r.store || r.store_name || '—'}</td>
      <td>${r.city || '—'}</td>
      <td style="color:var(--danger);font-weight:600">${fmtNum(r.unmet_units ?? r.unmet_quantity)}</td>
    </tr>
  `).join('');
}

function filterPlanTable() {
  const q   = document.getElementById('plan-search').value.toLowerCase().trim();
  const cat = document.getElementById('plan-category').value;
  const rows = (state.planRows || []).filter(r => {
    const matchCat  = !cat || r.category === cat;
    const matchText = !q  || [r.product, r.warehouse, r.store, r.reason].some(f => f && f.toLowerCase().includes(q));
    return matchCat && matchText;
  });
  renderPlanTable(rows);
}

function exportShipmentsCSV() {
  const q   = document.getElementById('plan-search').value.toLowerCase().trim();
  const cat = document.getElementById('plan-category').value;
  const rows = (state.planRows || []).filter(r => {
    const matchCat  = !cat || r.category === cat;
    const matchText = !q  || [r.product, r.warehouse, r.store].some(f => f && f.toLowerCase().includes(q));
    return matchCat && matchText;
  });
  if (!rows.length) { alert('No rows to export.'); return; }
  const headers = ['Product','Category','From Warehouse','To Store','City','Qty','Expiry (days)','Freight Cost (₹)','Reason'];
  const csvRows = [headers.join(',')];
  rows.forEach(r => {
    csvRows.push([
      `"${r.product || ''}"`,
      `"${r.category || ''}"`,
      `"${r.warehouse || ''}"`,
      `"${r.store || ''}"`,
      `"${r.city || ''}"`,
      r.quantity || '',
      r.expiry_days != null ? r.expiry_days : '',
      r.transport_cost != null ? r.transport_cost.toFixed(2) : '',
      `"${(r.reason || '').replace(/"/g, '""')}"`,
    ].join(','));
  });
  const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `optistock_shipments_${state.horizon}d.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ══════════════════════════════════════
   SECTION: INVENTORY
   Store real fields: store_name, city, product_name,
     current_stock, daily_demand, safety_stock,
     days_of_cover, risk_status
   WH real fields: batch_id, warehouse_name, product_name,
     storage, quantity, expiry_days, status, inventory_value
══════════════════════════════════════ */
async function loadInventory() {
  try {
    const [storeData, whData] = await Promise.all([
      apiFetch(`/api/inventory/stores?days=${state.horizon}`),
      apiFetch('/api/inventory/warehouses'),
    ]);
    state.storeInventory = storeData;
    state.whInventory    = whData;
    state.storeRows      = storeData;
    state.whRows         = whData;
    renderStoreTable(storeData);
    renderWhTable(whData);
    document.getElementById('store-count-label').textContent = `${storeData.length} store-product records`;
    document.getElementById('wh-count-label').textContent    = `${whData.length} warehouse batches`;
  } catch (err) {
    tableError('store-tbody', 8, err.message);
    tableError('wh-tbody',   8, err.message);
    console.error('[loadInventory]', err);
  }
}

function renderStoreTable(rows) {
  const tbody = document.getElementById('store-tbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No records.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td><strong>${r.store_name || '—'}</strong></td>
      <td>${r.city || '—'}</td>
      <td>${r.product_name || '—'}</td>
      <td><strong>${fmtNum(r.current_stock)}</strong></td>
      <td>${fmtNum(r.daily_demand)}</td>
      <td>${fmtNum(r.safety_stock)}</td>
      <td>${r.days_of_cover != null ? Number(r.days_of_cover).toFixed(1) : '—'}</td>
      <td><span class="${chipClass(r.risk_status)}">${r.risk_status || '—'}</span></td>
    </tr>
  `).join('');
}

function renderWhTable(rows) {
  const tbody = document.getElementById('wh-tbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No batches found.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="text-muted" style="font-family:monospace;font-size:.8rem">${r.batch_id || '—'}</td>
      <td>${r.warehouse_name || '—'}</td>
      <td><strong>${r.product_name || '—'}</strong></td>
      <td>${r.storage || '—'}</td>
      <td><strong>${fmtNum(r.quantity)}</strong></td>
      <td>${r.expiry_days != null ? r.expiry_days + ' d' : '—'}</td>
      <td><span class="${chipClass(r.status)}">${r.status || '—'}</span></td>
      <td style="color:var(--primary)">${fmtINR(r.inventory_value)}</td>
    </tr>
  `).join('');
}

function filterStoreTable() {
  const q      = document.getElementById('store-search').value.toLowerCase().trim();
  const status = document.getElementById('store-status-filter').value;
  const rows   = (state.storeRows || []).filter(r => {
    const matchStatus = !status || r.risk_status === status;
    const matchText   = !q || [r.store_name, r.city, r.product_name].some(f => f && f.toLowerCase().includes(q));
    return matchStatus && matchText;
  });
  renderStoreTable(rows);
}

function filterWhTable() {
  const q      = document.getElementById('wh-search').value.toLowerCase().trim();
  const status = document.getElementById('wh-status-filter').value;
  const rows   = (state.whRows || []).filter(r => {
    const matchStatus = !status || r.status === status;
    const matchText   = !q || [r.batch_id, r.warehouse_name, r.product_name].some(f => f && f.toLowerCase().includes(q));
    return matchStatus && matchText;
  });
  renderWhTable(rows);
}

function switchSubTab(tab) {
  document.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.sub-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('subtab-' + tab).classList.add('active');
  const panel = document.getElementById('inv-' + tab + '-panel');
  if (panel) panel.classList.remove('hidden');
}

/* ══════════════════════════════════════
   SECTION: FORECAST
══════════════════════════════════════ */
async function loadForecastMeta() {
  try {
    const data = await apiFetch('/api/meta');
    state.meta = data;
    const storeSel = document.getElementById('fc-store');
    storeSel.innerHTML = (data.stores || []).map(s =>
      `<option value="${s.id}">${s.name} (${s.city})</option>`
    ).join('');
    const prodSel = document.getElementById('fc-product');
    prodSel.innerHTML = (data.products || []).map(p =>
      `<option value="${p.id}">${p.name}</option>`
    ).join('');
    if (!document.getElementById('section-whatif').dataset.metaLoaded) {
      renderWhatIfCheckboxes(data.warehouses || []);
      document.getElementById('section-whatif').dataset.metaLoaded = 'true';
    }
  } catch (err) {
    console.error('[loadForecastMeta]', err);
  }
}

async function runForecast() {
  const storeId   = document.getElementById('fc-store').value;
  const productId = document.getElementById('fc-product').value;
  const days      = document.getElementById('fc-days').value;
  if (!storeId || !productId) { alert('Please select a store and a product.'); return; }
  document.getElementById('forecast-subtitle').textContent = 'Loading forecast…';
  try {
    const data = await apiFetch(`/api/forecast?store_id=${encodeURIComponent(storeId)}&product_id=${encodeURIComponent(productId)}&days=${days}`);
    renderForecastKPIs(data);
    renderForecastChart(data);
    const storeName   = document.getElementById('fc-store').selectedOptions[0]?.text || storeId;
    const productName = document.getElementById('fc-product').selectedOptions[0]?.text || productId;
    document.getElementById('forecast-subtitle').textContent =
      `${productName} · ${storeName} · ${days}-day horizon`;
  } catch (err) {
    document.getElementById('forecast-subtitle').textContent = '⚠️ ' + err.message;
    console.error('[runForecast]', err);
  }
}

function renderForecastKPIs(data) {
  const kpiDiv = document.getElementById('forecast-kpis');
  kpiDiv.classList.remove('hidden');
  const forecast = data.forecast || [];
  const totalExpected = forecast.reduce((s, f) => s + (f.predicted_demand || 0), 0);
  const dailyAvg      = forecast.length ? totalExpected / forecast.length : 0;
  const mae           = data.metrics?.mae  ?? data.mae  ?? null;
  const mape          = data.metrics?.mape ?? data.mape ?? null;
  const cards = [
    { icon: '📦', label: 'Total Expected (units)', value: fmtNum(Math.round(totalExpected)), accent: 'kpi-primary' },
    { icon: '📅', label: 'Daily Avg Demand',        value: fmtNum(Math.round(dailyAvg)),     accent: 'kpi-primary' },
    { icon: '📏', label: 'MAE (units)',              value: mae  != null ? Number(mae).toFixed(1) : '—', accent: '' },
    { icon: '🎯', label: 'MAPE',                    value: mape != null ? Number(mape).toFixed(1) + '%' : '—', accent: '' },
  ];
  kpiDiv.innerHTML = cards.map(c => `
    <div class="kpi-card ${c.accent}">
      <div class="kpi-icon">${c.icon}</div>
      <div class="kpi-body">
        <div class="kpi-value">${c.value}</div>
        <div class="kpi-label">${c.label}</div>
      </div>
    </div>
  `).join('');
}

function renderForecastChart(data) {
  const ctx = document.getElementById('forecast-chart').getContext('2d');
  if (state.forecastChart) { state.forecastChart.destroy(); state.forecastChart = null; }
  const forecast   = data.forecast || [];
  const labels     = forecast.map(f => f.date || f.day);
  const predicted  = forecast.map(f => f.predicted_demand);
  const lower      = forecast.map(f => f.lower_bound ?? f.ci_lower ?? null);
  const upper      = forecast.map(f => f.upper_bound ?? f.ci_upper ?? null);
  const historical = data.historical || [];
  const datasets = [];
  if (historical.length) {
    datasets.push({
      label: 'Historical Demand',
      data: historical.map(h => ({ x: h.date || h.day, y: h.demand ?? h.actual })),
      borderColor: '#94a3b8', backgroundColor: 'transparent',
      pointRadius: 2, borderDash: [4, 4], tension: 0.3,
    });
  }
  datasets.push({
    label: 'Predicted Demand',
    data: predicted, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.08)',
    fill: false, tension: 0.4, pointRadius: 3, pointBackgroundColor: '#2563eb',
  });
  if (upper.some(v => v != null)) {
    datasets.push({
      label: 'Upper Bound', data: upper,
      borderColor: 'rgba(37,99,235,0.2)', backgroundColor: 'rgba(37,99,235,0.08)',
      fill: '+1', tension: 0.4, pointRadius: 0, borderWidth: 1,
    });
  }
  if (lower.some(v => v != null)) {
    datasets.push({
      label: 'Lower Bound', data: lower,
      borderColor: 'rgba(37,99,235,0.2)', backgroundColor: 'rgba(37,99,235,0.08)',
      fill: false, tension: 0.4, pointRadius: 0, borderWidth: 1,
    });
  }
  state.forecastChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } } },
      scales: {
        x: { ticks: { font: { family: 'Inter', size: 11 } }, grid: { display: false } },
        y: { beginAtZero: false, ticks: { font: { family: 'Inter' } }, grid: { color: '#f1f5f9' } },
      },
    },
  });
}

/* ══════════════════════════════════════
   SECTION: WHAT-IF
══════════════════════════════════════ */
async function loadWhatIfMeta() {
  try {
    if (!state.meta) {
      const data = await apiFetch('/api/meta');
      state.meta = data;
    }
    renderWhatIfCheckboxes(state.meta.warehouses || []);
    if (!document.getElementById('fc-store').options.length && state.meta.stores) {
      document.getElementById('fc-store').innerHTML = state.meta.stores.map(s => `<option value="${s.id}">${s.name} (${s.city})</option>`).join('');
      document.getElementById('fc-product').innerHTML = state.meta.products.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    }
  } catch (err) {
    document.getElementById('wh-checkboxes').innerHTML = `<span style="color:var(--danger)">${err.message}</span>`;
    console.error('[loadWhatIfMeta]', err);
  }
}

function renderWhatIfCheckboxes(warehouses) {
  const container = document.getElementById('wh-checkboxes');
  if (!warehouses.length) { container.innerHTML = '<span>No warehouses found.</span>'; return; }
  container.innerHTML = warehouses.map(w => `
    <label class="checkbox-item">
      <input type="checkbox" value="${w.id}" />
      ${w.name} (${w.city})
    </label>
  `).join('');
}

async function runWhatIf() {
  const demandShock    = parseInt(document.getElementById('demand-slider').value, 10);
  const fuelMultiplier = parseFloat(document.getElementById('fuel-slider').value);
  const disabled = [...document.querySelectorAll('#wh-checkboxes input:checked')].map(c => c.value);
  const btn = document.querySelector('#section-whatif .btn-primary');
  btn.textContent = '⏳ Running…';
  btn.disabled    = true;
  const msgEl = document.getElementById('whatif-message');
  msgEl.className = 'whatif-message hidden';
  try {
    const result = await fetch('/api/scenario', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ horizon_days: state.horizon, demand_shock_pct: demandShock, fuel_multiplier: fuelMultiplier, disabled_warehouses: disabled }),
    });
    if (!result.ok) throw new Error(`HTTP ${result.status}`);
    const data = await result.json();
    renderWhatIfResults(data);
  } catch (err) {
    msgEl.className = 'whatif-message error';
    msgEl.textContent = '⚠️ Simulation failed: ' + err.message;
    msgEl.classList.remove('hidden');
    console.error('[runWhatIf]', err);
  } finally {
    btn.textContent = '🚀 Run Simulation';
    btn.disabled    = false;
  }
}

function renderWhatIfResults(d) {
  const kpiDiv    = document.getElementById('whatif-kpis');
  const plan      = d.plan || d;
  const benchmark = (d.plan && d.plan.benchmark) ? d.plan.benchmark : (d.benchmark || {});
  const cards = [
    { icon: '🚚', label: 'Units Shipped',       value: fmtNum(plan.units_shipped ?? d.units_shipped),   accent: 'kpi-primary' },
    { icon: '💸', label: 'Freight Cost',         value: fmtINR(plan.total_transport_cost ?? d.total_transport_cost), accent: '' },
    { icon: '⚠️', label: 'Unmet Demand',         value: fmtNum(plan.total_unmet_units ?? d.total_unmet_units),
      valueClass: (plan.total_unmet_units ?? d.total_unmet_units) > 0 ? 'value-warning' : 'value-success',
      accent:     (plan.total_unmet_units ?? d.total_unmet_units) > 0 ? 'kpi-warning' : 'kpi-success' },
    { icon: '📈', label: 'Fulfillment Rate',     value: fmtPct(benchmark.fulfillment_rate_ai ?? d.fulfillment_rate_ai), valueClass: 'value-success', accent: 'kpi-success' },
    { icon: '💰', label: 'Transport Savings',    value: fmtINR(benchmark.transport_savings ?? d.transport_savings), valueClass: 'value-success', accent: 'kpi-success' },
    { icon: '🎉', label: 'Net Economic Benefit', value: fmtINR(benchmark.total_economic_benefit ?? d.total_economic_benefit), valueClass: 'value-success', accent: 'kpi-success' },
  ];
  kpiDiv.innerHTML = cards.map(c => `
    <div class="kpi-card ${c.accent || ''}">
      <div class="kpi-icon">${c.icon}</div>
      <div class="kpi-body">
        <div class="kpi-value ${c.valueClass || ''}">${c.value}</div>
        <div class="kpi-label">${c.label}</div>
      </div>
    </div>
  `).join('');
  const msgEl = document.getElementById('whatif-message');
  msgEl.className = 'whatif-message success';
  msgEl.textContent = '✅ Simulation complete!';
  msgEl.classList.remove('hidden');
}

/* ══════════════════════════════════════
   SECTION: SHIPMENT MAP (Leaflet.js)
   Free OpenStreetMap tiles — no API key!
   Warehouses + existing stores + 5 new
   Maharashtra delivery locations
══════════════════════════════════════ */

// Fixed warehouse coordinates
const WAREHOUSES_STATIC = [
  { id: 'WH-MUM', name: 'Mumbai Central Mega-DC',         city: 'Mumbai',     lat: 19.0760, lng: 72.8777, type: 'warehouse' },
  { id: 'WH-PUN', name: 'Pune Regional Distribution Hub', city: 'Pune',       lat: 18.5204, lng: 73.8567, type: 'warehouse' },
  { id: 'WH-AHM', name: 'Ahmedabad Logistics Hub',        city: 'Ahmedabad',  lat: 23.0225, lng: 72.5714, type: 'warehouse' },
  { id: 'WH-SUR', name: 'Surat Coastal Depot',            city: 'Surat',      lat: 21.1702, lng: 72.8311, type: 'warehouse' },
];

// Existing stores
const STORES_STATIC = [
  { id: 'ST-MUM-S', name: 'Mumbai South Hypermarket',    city: 'Mumbai',     lat: 18.9388, lng: 72.8354, type: 'store' },
  { id: 'ST-MUM-N', name: 'Mumbai North Supercenter',    city: 'Mumbai',     lat: 19.1860, lng: 72.8485, type: 'store' },
  { id: 'ST-PUN-M', name: 'Pune Market Square Retail',   city: 'Pune',       lat: 18.5314, lng: 73.8446, type: 'store' },
  { id: 'ST-PUN-W', name: 'Pune West Mart',              city: 'Pune',       lat: 18.5074, lng: 73.8077, type: 'store' },
  { id: 'ST-THN',   name: 'Thane Regional Stockist',     city: 'Thane',      lat: 19.2183, lng: 72.9781, type: 'store' },
  { id: 'ST-NSH',   name: 'Nashik Fresh Direct',         city: 'Nashik',     lat: 19.9975, lng: 73.7898, type: 'store' },
  { id: 'ST-KOL',   name: 'Kolhapur Agro Mart',          city: 'Kolhapur',   lat: 16.7050, lng: 74.2433, type: 'store' },
  { id: 'ST-AHM-P', name: 'Ahmedabad Prime Superstore',  city: 'Ahmedabad',  lat: 23.0338, lng: 72.5850, type: 'store' },
  { id: 'ST-SUR-R', name: 'Surat City Mart',             city: 'Surat',      lat: 21.1959, lng: 72.8193, type: 'store' },
  { id: 'ST-VAD',   name: 'Vadodara Express Outlet',     city: 'Vadodara',   lat: 22.3072, lng: 73.1812, type: 'store' },
];

function initMap() {
  // Destroy existing map instance if re-entering the section
  if (state.leafletMap) {
    state.leafletMap.remove();
    state.leafletMap = null;
  }

  // Create Leaflet map centered on Maharashtra
  const map = L.map('shipment-map').setView([18.5, 73.5], 7);
  state.leafletMap = map;

  // OpenStreetMap tiles (free, no API key required)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(map);

  // Custom icons
  const warehouseIcon = L.divIcon({
    className: '',
    html: '<div style="background:#1e293b;color:#fff;border-radius:8px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 2px 8px rgba(0,0,0,0.3);border:2px solid #2563eb">🏭</div>',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -20],
  });
  const storeIcon = L.divIcon({
    className: '',
    html: '<div style="background:#2563eb;color:#fff;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 2px 8px rgba(37,99,235,0.4);border:2px solid #fff">🏪</div>',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -18],
  });
  const newLocIcon = L.divIcon({
    className: '',
    html: '<div style="background:#16a34a;color:#fff;border-radius:50%;width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 8px rgba(22,163,74,0.5);border:2px solid #fff;animation:pulse-green 2s infinite">📍</div>',
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -20],
  });

  // Plot warehouses
  WAREHOUSES_STATIC.forEach(wh => {
    const marker = L.marker([wh.lat, wh.lng], { icon: warehouseIcon }).addTo(map);
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:180px">
        <strong style="font-size:14px">🏭 ${wh.name}</strong><br/>
        <span style="color:#64748b;font-size:12px">📍 ${wh.city}</span><br/>
        <span style="display:inline-block;margin-top:6px;padding:2px 8px;background:#1e293b;color:#fff;border-radius:4px;font-size:11px">Distribution Centre</span>
      </div>
    `);
  });

  // Plot existing stores
  STORES_STATIC.forEach(st => {
    const marker = L.marker([st.lat, st.lng], { icon: storeIcon }).addTo(map);
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:160px">
        <strong style="font-size:13px">🏪 ${st.name}</strong><br/>
        <span style="color:#64748b;font-size:12px">📍 ${st.city}</span><br/>
        <span style="display:inline-block;margin-top:6px;padding:2px 8px;background:#2563eb;color:#fff;border-radius:4px;font-size:11px">Retail Store</span>
      </div>
    `);
  });

  // Plot NEW delivery locations
  NEW_LOCATIONS.forEach(loc => {
    const marker = L.marker([loc.lat, loc.lng], { icon: newLocIcon }).addTo(map);
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:180px">
        <strong style="font-size:14px;color:#16a34a">🆕 ${loc.name}</strong><br/>
        <span style="color:#64748b;font-size:12px">📍 ${loc.city}, Maharashtra</span><br/>
        <span style="display:inline-block;margin-top:6px;padding:2px 8px;background:#16a34a;color:#fff;border-radius:4px;font-size:11px">New Delivery Location</span>
      </div>
    `).openPopup();
  });

  // Draw shipment routes from Pune DC to new locations
  const puneWH = WAREHOUSES_STATIC.find(w => w.id === 'WH-PUN');
  const mumWH  = WAREHOUSES_STATIC.find(w => w.id === 'WH-MUM');

  // Route colours for each new location
  const routeColors = ['#e11d48', '#7c3aed', '#0891b2', '#ea580c', '#059669'];

  NEW_LOCATIONS.forEach((loc, i) => {
    // Primary route: Pune DC → new location
    const routeLine = L.polyline(
      [[puneWH.lat, puneWH.lng], [loc.lat, loc.lng]],
      { color: routeColors[i], weight: 3, opacity: 0.75, dashArray: '8, 6' }
    ).addTo(map);
    routeLine.bindTooltip(
      `🚚 Pune DC → ${loc.city}<br/>Est. route distance`,
      { sticky: true, className: 'route-tooltip' }
    );

    // Secondary route: Mumbai DC → new location (dashed, lighter)
    L.polyline(
      [[mumWH.lat, mumWH.lng], [loc.lat, loc.lng]],
      { color: routeColors[i], weight: 1.5, opacity: 0.35, dashArray: '4, 8' }
    ).addTo(map);
  });

  // Also draw routes from Pune DC → existing stores (for context)
  STORES_STATIC.filter(s => s.city === 'Pune' || s.city === 'Kolhapur').forEach(st => {
    L.polyline(
      [[puneWH.lat, puneWH.lng], [st.lat, st.lng]],
      { color: '#2563eb', weight: 2, opacity: 0.4, dashArray: '6, 4' }
    ).addTo(map);
  });

  // Render the locations table
  renderLocationsTable();

  // Render the live fleet stops cards
  renderFleetStops();
}

function reloadMap() {
  initMap();
}

/* ══════════════════════════════════════
   FLEET DISPATCH & STOPS TRACKER
   (Pune, Satara, Kolhapur, Sangli, Karad)
══════════════════════════════════════ */
async function fetchDeliveryStops() {
  try {
    const data = await apiFetch('/api/delivery/stops');
    if (data && typeof data === 'object') {
      liveDeliveryStops = { ...liveDeliveryStops, ...data };
    }
  } catch (err) {
    console.warn('[fetchDeliveryStops] Using in-memory fallback', err);
  }
}

async function renderFleetStops() {
  await fetchDeliveryStops();
  const container = document.getElementById('fleet-stops-cards');
  if (!container) return;

  const stopKeys = Object.keys(liveDeliveryStops);
  let completedCount = 0;

  container.innerHTML = stopKeys.map(locId => {
    const stop = liveDeliveryStops[locId];
    const isDelivered = stop.status === 'Delivered';
    if (isDelivered) completedCount++;

    const statusChipClass = isDelivered ? 'chip-healthy' :
      (stop.status === 'Out for Delivery' ? 'chip-warning' : 'chip-primary');

    return `
      <div class="fleet-stop-card" id="stop-card-${locId}" style="${isDelivered ? 'border-color:#86efac;background:#f0fdf4;' : ''}">
        <div class="fsc-header">
          <span class="fsc-city">📍 ${stop.city}</span>
          <span class="chip ${statusChipClass}">${stop.status}</span>
        </div>
        <div class="fsc-meta">
          <div><strong>Driver:</strong> ${stop.driver}</div>
          <div><strong>Vehicle:</strong> ${stop.vehicle}</div>
          <div><strong>ETA:</strong> ${stop.eta}</div>
        </div>
        <div class="fsc-actions">
          <button class="fsc-btn" onclick="updateStopStatus('${locId}', 'In Transit')">In Transit</button>
          <button class="fsc-btn delivered" onclick="updateStopStatus('${locId}', 'Delivered')">✓ Delivered</button>
        </div>
      </div>
    `;
  }).join('');

  const liveBadge = document.getElementById('fleet-live-badge');
  if (liveBadge) {
    liveBadge.textContent = `⚡ ${stopKeys.length - completedCount} In Progress · ${completedCount} Delivered`;
  }
}

async function updateStopStatus(locId, newStatus) {
  if (liveDeliveryStops[locId]) {
    liveDeliveryStops[locId].status = newStatus;
    if (newStatus === 'Delivered') {
      liveDeliveryStops[locId].eta = 'Completed';
    }
  }

  // Update UI immediately
  renderFleetStops();
  renderLocationsTable();

  // Sync with backend API
  try {
    await fetch('/api/delivery/stops', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loc_id: locId, status: newStatus })
    });
  } catch (err) {
    console.error('[updateStopStatus]', err);
  }
}

function renderLocationsTable() {
  const tbody = document.getElementById('locations-tbody');
  if (!tbody) return;

  const allLocations = [
    ...WAREHOUSES_STATIC.map(w => ({ ...w, status: 'Active DC', shipments: 'Multiple' })),
    ...STORES_STATIC.map(s => ({ ...s, status: 'Active Store', shipments: 'Receiving' })),
    ...NEW_LOCATIONS.map(l => {
      const live = liveDeliveryStops[l.id];
      const liveStatus = live ? live.status : 'Planned';
      return { ...l, status: liveStatus, shipments: live ? `${live.driver} (${live.vehicle})` : 'Dispatched' };
    }),
  ];

  tbody.innerHTML = allLocations.map(loc => {
    const typeLabel = loc.type === 'warehouse' ? '🏭 Warehouse' :
                      loc.type === 'New Delivery' ? '📍 New Location' : '🏪 Store';
    const isNew = loc.type === 'New Delivery';
    const rowClass  = isNew ? 'style="background:#f0fdf4"' : '';
    const statusChip = loc.status === 'Delivered' ? 'chip-healthy' :
                       (loc.status === 'Out for Delivery' ? 'chip-warning' : (isNew ? 'chip-primary' : 'chip'));

    return `
      <tr ${rowClass}>
        <td><strong>${loc.name}</strong></td>
        <td>${typeLabel}</td>
        <td>${loc.city}${loc.type === 'New Delivery' ? ', Maharashtra' : ''}</td>
        <td style="font-family:monospace;font-size:.8rem">${Number(loc.lat).toFixed(4)}, ${Number(loc.lng).toFixed(4)}</td>
        <td><span class="chip ${statusChip}">${loc.status}</span></td>
        <td>${loc.shipments}</td>
      </tr>
    `;
  }).join('');
}

/* ══════════════════════════════════════
   INIT
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  // Check for saved role preference
  let savedRole = 'admin';
  try {
    savedRole = localStorage.getItem('optistock_user_role') || 'admin';
  } catch(e) {}

  switchUserRole(savedRole);
});
