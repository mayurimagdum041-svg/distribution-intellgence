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
    badge: 'Administrator',
    avatar: 'AD',
    color: '#2563eb',
    allowedSections: ['overview', 'automation', 'approvals', 'alerts', 'distribution', 'inventory', 'forecast', 'whatif', 'map'],
    defaultSection: 'overview',
    bannerIcon: '',
    bannerTitle: 'Logged in as Administrator (Full Access)',
    bannerDesc: 'Full executive control: global network KPIs, SciPy HiGHS MILP solver, automation engine, manager approvals, and all reports.'
  },
  warehouse: {
    key: 'warehouse',
    name: 'Pune Regional DC Head',
    badge: 'Warehouse Manager',
    avatar: 'WH',
    color: '#d97706',
    allowedSections: ['inventory', 'approvals', 'alerts', 'distribution', 'map'],
    defaultSection: 'inventory',
    defaultSubTab: 'warehouses',
    bannerIcon: '',
    bannerTitle: 'Logged in as Warehouse Manager (Pune Hub)',
    bannerDesc: 'Monitoring batch shelf-life (FEFO radar), FEFO expiry rescue offloading, cold-chain pallet storage, and outbound manifests.'
  },
  retail: {
    key: 'retail',
    name: 'Store Operations Head',
    badge: 'Retail Store Manager',
    avatar: 'RT',
    color: '#16a34a',
    allowedSections: ['inventory', 'approvals', 'alerts', 'distribution', 'forecast'],
    defaultSection: 'inventory',
    defaultSubTab: 'stores',
    bannerIcon: '',
    bannerTitle: 'Logged in as Retail Store Manager',
    bannerDesc: 'Tracking store on-hand stock, Days of Cover, Reorder Points (ROP), auto-replenishment approvals, and ML demand forecasts.'
  },
  delivery: {
    key: 'delivery',
    name: 'Maharashtra Corridor Fleet',
    badge: 'Delivery Fleet',
    avatar: 'DL',
    color: '#7c3aed',
    allowedSections: ['map', 'alerts', 'distribution'],
    defaultSection: 'map',
    bannerIcon: '',
    bannerTitle: 'Logged in as Delivery Partner & Driver Fleet',
    bannerDesc: 'Live dispatch route navigation, SLA deadline audit monitoring, and delivery checkpoints for Pune, Satara, Kolhapur, Sangli, and Karad.'
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
   ROLE SWITCHING & PIN ACCESS CONTROL
══════════════════════════════════════ */
const PIN_CONFIG = {
  admin:     { pin: '1111', title: 'Administrator',          icon: 'AD', color: '#2563eb' },
  warehouse: { pin: '2222', title: 'Warehouse Manager',      icon: 'WH', color: '#d97706' },
  retail:    { pin: '3333', title: 'Retail Store Manager',   icon: 'RT', color: '#16a34a' },
  delivery:  { pin: '4444', title: 'Delivery Fleet Partner', icon: 'DL', color: '#7c3aed' },
};

let authState = {
  pendingRole: null,
  enteredPin: '',
  isLocked: false,
};

function switchUserRole(roleKey) {
  // If already logged in as this role, do nothing
  if (state.currentUser === roleKey && !authState.isLocked) {
    return;
  }
  // Require 4-digit PIN to switch to the new role
  promptPinForRole(roleKey);
}

function promptPinForRole(roleKey) {
  const role = USER_ROLES[roleKey];
  const pinInfo = PIN_CONFIG[roleKey];
  if (!role || !pinInfo) return;

  authState.pendingRole = roleKey;
  authState.enteredPin = '';

  // Switch modal view to PIN pad
  const selectView = document.getElementById('modal-role-select-view');
  const pinView    = document.getElementById('modal-pin-entry-view');
  if (selectView) selectView.classList.add('hidden');
  if (pinView)    pinView.classList.remove('hidden');

  // Update PIN modal headers and role display
  const titleEl    = document.getElementById('pin-modal-title');
  const roleIcon   = document.getElementById('pin-role-icon');
  const roleName   = document.getElementById('pin-role-name');
  const roleDesc   = document.getElementById('pin-role-desc');
  const hintText   = document.getElementById('pin-hint-text');
  const errorAlert = document.getElementById('pin-error-alert');

  if (titleEl)  titleEl.textContent = `Unlock ${pinInfo.title}`;
  if (roleIcon) {
    roleIcon.textContent = pinInfo.icon;
    roleIcon.style.background = `${pinInfo.color}15`;
    roleIcon.style.color = pinInfo.color;
  }
  if (roleName) roleName.textContent = role.name;
  if (roleDesc) roleDesc.textContent = `Role: ${role.badge} · Enter 4-digit PIN`;
  if (hintText) hintText.innerHTML = `Quick PIN: <strong>${pinInfo.pin}</strong>`;
  if (errorAlert) {
    errorAlert.textContent = '';
    errorAlert.classList.add('hidden');
  }

  updatePinDisplay();
  openRoleModal();
}

function enterPinDigit(digit) {
  if (authState.enteredPin.length >= 4) return;
  authState.enteredPin += String(digit);
  updatePinDisplay();

  // If 4 digits entered, automatically verify PIN after slight delay
  if (authState.enteredPin.length === 4) {
    setTimeout(verifyEnteredPin, 180);
  }
}

function backspacePin() {
  if (authState.enteredPin.length > 0) {
    authState.enteredPin = authState.enteredPin.slice(0, -1);
    updatePinDisplay();
  }
}

function clearPin() {
  authState.enteredPin = '';
  updatePinDisplay();
  const errorAlert = document.getElementById('pin-error-alert');
  if (errorAlert) errorAlert.classList.add('hidden');
}

function updatePinDisplay() {
  for (let i = 0; i < 4; i++) {
    const box = document.getElementById(`pin-box-${i}`);
    if (!box) continue;
    if (i < authState.enteredPin.length) {
      box.textContent = '●';
      box.classList.add('filled');
      box.classList.remove('active');
    } else if (i === authState.enteredPin.length) {
      box.textContent = '';
      box.classList.remove('filled');
      box.classList.add('active');
    } else {
      box.textContent = '';
      box.classList.remove('filled');
      box.classList.remove('active');
    }
  }
}

async function verifyEnteredPin() {
  const roleKey = authState.pendingRole;
  const pin = authState.enteredPin;
  const pinInfo = PIN_CONFIG[roleKey];
  const errorAlert = document.getElementById('pin-error-alert');
  const dotsWrap = document.getElementById('pin-dots-wrap');

  if (!roleKey || pin.length !== 4) return;

  let isValid = false;

  // Verify with backend API
  try {
    const res = await fetch('/api/auth/verify-pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: roleKey, pin: pin })
    });
    if (res.ok) {
      isValid = true;
    }
  } catch (err) {
    console.warn('[verifyEnteredPin] Falling back to local check', err);
  }

  // Fallback to client-side PIN check if offline
  if (!isValid && pinInfo && pinInfo.pin === pin) {
    isValid = true;
  }

  if (isValid) {
    // Success: Flash green
    for (let i = 0; i < 4; i++) {
      const box = document.getElementById(`pin-box-${i}`);
      if (box) {
        box.style.borderColor = '#16a34a';
        box.style.color = '#16a34a';
        box.style.background = '#dcfce7';
      }
    }

    setTimeout(() => {
      // Reset box styles
      for (let i = 0; i < 4; i++) {
        const box = document.getElementById(`pin-box-${i}`);
        if (box) {
          box.style.borderColor = '';
          box.style.color = '';
          box.style.background = '';
        }
      }

      applyUserRole(roleKey);
      authState.isLocked = false;
      closeRoleModal();
    }, 280);

  } else {
    // Failure: Shake animation & alert
    if (dotsWrap) {
      dotsWrap.classList.add('shake');
      setTimeout(() => dotsWrap.classList.remove('shake'), 450);
    }

    if (errorAlert) {
      errorAlert.textContent = `Invalid PIN for ${pinInfo ? pinInfo.title : 'role'}. Try: ${pinInfo ? pinInfo.pin : '1111'}`;
      errorAlert.classList.remove('hidden');
    }

    // Clear after animation
    setTimeout(() => {
      clearPin();
    }, 450);
  }
}

function cancelPinPrompt() {
  authState.enteredPin = '';
  const selectView = document.getElementById('modal-role-select-view');
  const pinView    = document.getElementById('modal-pin-entry-view');
  if (selectView) selectView.classList.remove('hidden');
  if (pinView)    pinView.classList.add('hidden');
}

function lockSession() {
  authState.isLocked = true;
  openRoleModal();
}

function applyUserRole(roleKey) {
  const role = USER_ROLES[roleKey];
  if (!role) return;

  state.currentUser = roleKey;
  try {
    sessionStorage.setItem('optistock_auth_role', roleKey);
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

  // Filter Nav Section Labels so empty groups don't show
  document.querySelectorAll('.nav-section-label').forEach(label => {
    let nextEl = label.nextElementSibling;
    let hasVisible = false;
    while (nextEl && !nextEl.classList.contains('nav-section-label')) {
      if (nextEl.classList.contains('nav-link') && nextEl.style.display !== 'none') {
        hasVisible = true;
        break;
      }
      nextEl = nextEl.nextElementSibling;
    }
    label.style.display = hasVisible ? 'block' : 'none';
  });

  // Update Role Notification Banner
  const banner = document.getElementById('role-welcome-banner');
  const iconEl = document.getElementById('rwb-icon');
  const titleEl= document.getElementById('rwb-title');
  const descEl = document.getElementById('rwb-desc');

  if (banner) {
    banner.style.borderLeftColor = role.color;
    // If not previously dismissed by user in this session, show it
    if (!sessionStorage.getItem('optistock_banner_dismissed')) {
      banner.classList.remove('banner-dismissed');
    }
  }
  if (iconEl) iconEl.textContent = role.bannerIcon;
  if (titleEl) titleEl.textContent = role.bannerTitle;
  if (descEl) descEl.textContent = role.bannerDesc;
}

function dismissBanner() {
  const banner = document.getElementById('role-welcome-banner');
  if (banner) {
    banner.classList.add('banner-dismissed');
    try { sessionStorage.setItem('optistock_banner_dismissed', 'true'); } catch(e) {}
  }
}

function openRoleModal() {
  const modal = document.getElementById('role-modal');
  if (modal) modal.classList.remove('hidden');

  // By default show role selector unless already in pin view
  const selectView = document.getElementById('modal-role-select-view');
  const pinView    = document.getElementById('modal-pin-entry-view');
  if (!authState.pendingRole) {
    if (selectView) selectView.classList.remove('hidden');
    if (pinView)    pinView.classList.add('hidden');
  }
}

function closeRoleModal() {
  // If locked, cannot close without unlocking
  if (authState.isLocked) return;

  const modal = document.getElementById('role-modal');
  if (modal) modal.classList.add('hidden');
  cancelPinPrompt();
}

function selectRoleAndClose(roleKey) {
  promptPinForRole(roleKey);
}

// Global Keyboard Handler for PIN numpad
document.addEventListener('keydown', (e) => {
  const pinView = document.getElementById('modal-pin-entry-view');
  if (!pinView || pinView.classList.contains('hidden')) return;

  if (e.key >= '0' && e.key <= '9') {
    e.preventDefault();
    enterPinDigit(e.key);
  } else if (e.key === 'Backspace') {
    e.preventDefault();
    backspacePin();
  } else if (e.key === 'Enter') {
    e.preventDefault();
    verifyEnteredPin();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    cancelPinPrompt();
  }
});

/* ══════════════════════════════════════
   NAVIGATION
══════════════════════════════════════ */
const SECTION_META = {
  overview:     { title: 'Overview',      subtitle: 'Key performance indicators at a glance' },
  automation:   { title: 'Automation Engine', subtitle: 'Autonomous background workflows, scheduling controls, and dry-run execution engine' },
  approvals:    { title: 'Manager Approvals', subtitle: 'Authorize or reject store replenishment orders and FEFO expiry rescue transfers' },
  alerts:       { title: 'Alert Center', subtitle: 'Automated database-backed alerts with deduplication, severity ranking, and action recommendations' },
  distribution: { title: 'Distribution',  subtitle: 'AI-optimised shipment plan and multi-echelon sourcing recommendations' },
  inventory:    { title: 'Inventory',     subtitle: 'Store health and warehouse batch status' },
  forecast:     { title: 'Forecast',      subtitle: 'ML-driven demand forecast by store and product' },
  whatif:       { title: 'What-If',       subtitle: 'Run scenario simulations with custom shocks' },
  map:          { title: 'Shipment Map',  subtitle: 'Live route map and automated delivery delay monitoring across Maharashtra' },
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
  const icon = document.querySelector('.refresh-icon');
  if (icon) {
    icon.classList.remove('spinning');
    void icon.offsetWidth;
    icon.classList.add('spinning');
    setTimeout(() => icon.classList.remove('spinning'), 650);
  }
  state.summary = null;
  state.plan = null;
  state.storeInventory = null;
  state.whInventory = null;
  updateGlobalBadges();
  lazyLoad(state.currentSection);
  showToast('Live dashboard data updated', 'info', 'Refreshed');
}

function lazyLoad(section) {
  switch (section) {
    case 'overview':     if (!state.summary)       loadSummary();             break;
    case 'automation':   loadAutomationStatus();   loadAutomationHistory();   break;
    case 'approvals':    loadApprovals();                                     break;
    case 'alerts':       loadAlerts();                                        break;
    case 'distribution': if (!state.plan) loadPlan(); loadDistributionOptions(); break;
    case 'inventory':    if (!state.storeInventory) loadInventory();           break;
    case 'forecast':     if (!state.meta)           loadForecastMeta();        break;
    case 'whatif':       if (!state.meta)           loadWhatIfMeta();          break;
    case 'map':          initMap(); loadDeliveryMonitoring();                 break;
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
  if (el) el.innerHTML = `<tr><td colspan="${colSpan}" class="loading-row" style="color:#dc2626">${msg}</td></tr>`;
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
      `<div style="color:var(--danger);padding:1rem;grid-column:1/-1">Failed to load KPIs: ${err.message}</div>`;
    console.error('[loadSummary]', err);
  }
}

function renderKPICards(d) {
  const svgIcons = {
    box: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>',
    money: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>',
    critical: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
    warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
    truck: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>',
    chart: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>',
    savings: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>',
    shield: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>'
  };

  const cards = [
    { icon: svgIcons.box, label: 'Total Stock Units',    value: fmtNum(d.total_inventory_units), accent: 'kpi-primary' },
    { icon: svgIcons.money, label: 'Stock Value',           value: fmtINR(d.total_inventory_value), accent: 'kpi-primary' },
    { icon: svgIcons.critical, label: 'Critical Stores',       value: fmtNum(d.critical_stockouts),
      valueClass: d.critical_stockouts > 0 ? 'value-danger' : '',
      accent: d.critical_stockouts > 0 ? 'kpi-danger' : '' },
    { icon: svgIcons.warning, label: 'At-Risk Stores',        value: fmtNum(d.warning_stockouts),
      valueClass: d.warning_stockouts > 0 ? 'value-warning' : '',
      accent: d.warning_stockouts > 0 ? 'kpi-warning' : '' },
    { icon: svgIcons.truck, label: 'Shipments Planned',     value: fmtNum(d.shipment_count),       accent: 'kpi-primary' },
    { icon: svgIcons.chart, label: 'Fulfillment Rate (AI)', value: fmtPct(d.fulfillment_rate_ai),  valueClass: 'value-success', accent: 'kpi-success' },
    { icon: svgIcons.savings, label: 'Transport Savings',     value: fmtINR(d.transport_savings),    valueClass: 'value-success', accent: 'kpi-success' },
    { icon: svgIcons.shield, label: 'Spoilage Prevented',   value: fmtINR(d.spoilage_averted_savings), valueClass: 'value-success', accent: 'kpi-success' },
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
    tbody.innerHTML = '<tr><td colspan="4" class="loading-row" style="color:var(--success)">All demand fulfilled!</td></tr>';
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
  if (!rows.length) { showToast('No shipment rows to export matching your filter.', 'warning', 'Export Notice'); return; }
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
  if (!storeId || !productId) { showToast('Please select both a store and a product first.', 'warning', 'Selection Required'); return; }
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
    document.getElementById('forecast-subtitle').textContent = err.message;
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
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>', label: 'Total Expected (units)', value: fmtNum(Math.round(totalExpected)), accent: 'kpi-primary' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>', label: 'Daily Avg Demand',        value: fmtNum(Math.round(dailyAvg)),     accent: 'kpi-primary' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>', label: 'MAE (units)',              value: mae  != null ? Number(mae).toFixed(1) : '—', accent: '' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>', label: 'MAPE',                    value: mape != null ? Number(mape).toFixed(1) + '%' : '—', accent: '' },
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
    msgEl.textContent = 'Simulation failed: ' + err.message;
    msgEl.classList.remove('hidden');
    console.error('[runWhatIf]', err);
  } finally {
    btn.textContent = 'Run Simulation';
    btn.disabled    = false;
  }
}

function renderWhatIfResults(d) {
  const kpiDiv    = document.getElementById('whatif-kpis');
  const plan      = d.plan || d;
  const benchmark = (d.plan && d.plan.benchmark) ? d.plan.benchmark : (d.benchmark || {});
  const cards = [
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>', label: 'Units Shipped',       value: fmtNum(plan.units_shipped ?? d.units_shipped),   accent: 'kpi-primary' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>', label: 'Freight Cost',         value: fmtINR(plan.total_transport_cost ?? d.total_transport_cost), accent: '' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>', label: 'Unmet Demand',         value: fmtNum(plan.total_unmet_units ?? d.total_unmet_units),
      valueClass: (plan.total_unmet_units ?? d.total_unmet_units) > 0 ? 'value-warning' : 'value-success',
      accent:     (plan.total_unmet_units ?? d.total_unmet_units) > 0 ? 'kpi-warning' : 'kpi-success' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>', label: 'Fulfillment Rate',     value: fmtPct(benchmark.fulfillment_rate_ai ?? d.fulfillment_rate_ai), valueClass: 'value-success', accent: 'kpi-success' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>', label: 'Transport Savings',    value: fmtINR(benchmark.transport_savings ?? d.transport_savings), valueClass: 'value-success', accent: 'kpi-success' },
    { icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>', label: 'Net Economic Benefit', value: fmtINR(benchmark.total_economic_benefit ?? d.total_economic_benefit), valueClass: 'value-success', accent: 'kpi-success' },
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
  msgEl.textContent = 'Simulation complete!';
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
    html: '<div style="background:#1e293b;color:#fff;border-radius:8px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.3);border:2px solid #2563eb"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M3 9h18M9 21V9"></path></svg></div>',
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -20],
  });
  const storeIcon = L.divIcon({
    className: '',
    html: '<div style="background:#2563eb;color:#fff;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(37,99,235,0.4);border:2px solid #fff"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg></div>',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -18],
  });
  const newLocIcon = L.divIcon({
    className: '',
    html: '<div style="background:#16a34a;color:#fff;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(22,163,74,0.5);border:2px solid #fff;animation:pulse-green 2s infinite"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z"></path></svg></div>',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -20],
  });

  // Plot warehouses
  WAREHOUSES_STATIC.forEach(wh => {
    const marker = L.marker([wh.lat, wh.lng], { icon: warehouseIcon }).addTo(map);
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:180px">
        <strong style="font-size:14px">${wh.name}</strong><br/>
        <span style="color:#64748b;font-size:12px">${wh.city}</span><br/>
        <span style="display:inline-block;margin-top:6px;padding:2px 8px;background:#1e293b;color:#fff;border-radius:4px;font-size:11px">Distribution Centre</span>
      </div>
    `);
  });

  // Plot existing stores
  STORES_STATIC.forEach(st => {
    const marker = L.marker([st.lat, st.lng], { icon: storeIcon }).addTo(map);
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:160px">
        <strong style="font-size:13px">${st.name}</strong><br/>
        <span style="color:#64748b;font-size:12px">${st.city}</span><br/>
        <span style="display:inline-block;margin-top:6px;padding:2px 8px;background:#2563eb;color:#fff;border-radius:4px;font-size:11px">Retail Store</span>
      </div>
    `);
  });

  // Plot NEW delivery locations
  NEW_LOCATIONS.forEach(loc => {
    const marker = L.marker([loc.lat, loc.lng], { icon: newLocIcon }).addTo(map);
    marker.bindPopup(`
      <div style="font-family:Inter,sans-serif;min-width:180px">
        <strong style="font-size:14px;color:#16a34a">${loc.name}</strong><br/>
        <span style="color:#64748b;font-size:12px">${loc.city}, Maharashtra</span><br/>
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
      `Pune DC → ${loc.city}<br/>Est. route distance`,
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
          <span class="fsc-city">${stop.city}</span>
          <span class="chip ${statusChipClass}">${stop.status}</span>
        </div>
        <div class="fsc-meta">
          <div><strong>Driver:</strong> ${stop.driver}</div>
          <div><strong>Vehicle:</strong> ${stop.vehicle}</div>
          <div><strong>ETA:</strong> ${stop.eta}</div>
        </div>
        <div class="fsc-actions">
          <button class="fsc-btn" onclick="updateStopStatus('${locId}', 'In Transit')">In Transit</button>
          <button class="fsc-btn delivered" onclick="updateStopStatus('${locId}', 'Delivered')">Delivered</button>
        </div>
      </div>
    `;
  }).join('');

  const liveBadge = document.getElementById('fleet-live-badge');
  if (liveBadge) {
    liveBadge.textContent = `${stopKeys.length - completedCount} In Progress · ${completedCount} Delivered`;
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
    const typeLabel = loc.type === 'warehouse' ? 'Warehouse' :
                      loc.type === 'New Delivery' ? 'New Location' : 'Store';
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
   SMOOTH FLOATING TOAST NOTIFICATIONS
══════════════════════════════════════ */
function showToast(message, type = 'info', title = '') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>',
    error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
    warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
    info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
  };

  const titles = {
    success: title || 'Action Completed',
    error: title || 'Attention Required',
    warning: title || 'Warning Notice',
    info: title || 'System Update'
  };

  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${icons[type] || icons.info}</div>
    <div class="toast-content">
      <div class="toast-title">${titles[type]}</div>
      <div class="toast-msg">${message}</div>
    </div>
    <button class="toast-close" title="Dismiss">&times;</button>
  `;

  const closeBtn = toast.querySelector('.toast-close');
  const dismiss = () => {
    toast.classList.add('toast-hiding');
    setTimeout(() => toast.remove(), 220);
  };

  closeBtn.addEventListener('click', dismiss);
  container.appendChild(toast);

  // Auto-dismiss after 4 seconds
  setTimeout(dismiss, 4000);
}

/* ══════════════════════════════════════
   SMOOTH ACTION CONFIRMATION MODAL
══════════════════════════════════════ */
let actionDialogResolver = null;

function showActionDialog({ title, subtitle, message, inputLabel = 'Manager Notes:', defaultValue = '', confirmText = 'Confirm Decision', showInput = true }) {
  return new Promise((resolve) => {
    actionDialogResolver = resolve;
    const modal = document.getElementById('action-dialog-modal');
    const titleEl = document.getElementById('action-dialog-title');
    const subEl = document.getElementById('action-dialog-subtitle');
    const msgEl = document.getElementById('action-dialog-message');
    const labelEl = document.getElementById('action-dialog-input-label');
    const inputEl = document.getElementById('action-dialog-input');
    const groupEl = document.getElementById('action-dialog-input-group');
    const confirmBtn = document.getElementById('action-dialog-confirm-btn');

    if (titleEl) titleEl.textContent = title || 'Manager Authorization';
    if (subEl) subEl.textContent = subtitle || 'Review and submit your decision';
    if (msgEl) msgEl.innerHTML = message || '';
    if (labelEl) labelEl.textContent = inputLabel;
    if (inputEl) inputEl.value = defaultValue;
    if (groupEl) groupEl.style.display = showInput ? 'block' : 'none';
    if (confirmBtn) confirmBtn.textContent = confirmText;

    if (modal) modal.classList.remove('hidden');
    if (showInput && inputEl) {
      setTimeout(() => inputEl.focus(), 120);
    }
  });
}

function closeActionDialog(isConfirmed) {
  const modal = document.getElementById('action-dialog-modal');
  const inputEl = document.getElementById('action-dialog-input');
  const value = inputEl ? inputEl.value.trim() : '';

  if (modal) modal.classList.add('hidden');

  if (actionDialogResolver) {
    actionDialogResolver({ confirmed: Boolean(isConfirmed), value: value });
    actionDialogResolver = null;
  }
}

/* ══════════════════════════════════════
   AUTOMATION ENGINE & WORKFLOWS
══════════════════════════════════════ */
let automationState = {
  workflows: [],
  history: [],
  replenishments: [],
  expiryTransfers: [],
  alerts: [],
  distributionOptions: [],
  deliveries: [],
};

const WORKFLOW_ICONS = {
  auto_replenishment: { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>', bg: '#eff6ff', color: '#2563eb' },
  expiry_rescue:      { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>', bg: '#fef3c7', color: '#d97706' },
  distribution_optimization: { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line></svg>', bg: '#dcfce7', color: '#16a34a' },
  delivery_monitoring: { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>', bg: '#f3e8ff', color: '#7c3aed' }
};

async function updateGlobalBadges() {
  try {
    const res = await fetch('/api/automation/status');
    if (!res.ok) return;
    const data = await res.json();
    const m = data.metrics || {};

    const alertCount = m.active_alerts || 0;
    const pendingTotal = (m.pending_replenishments || 0) + (m.pending_expiry_rescues || 0);

    const alertBadge = document.getElementById('nav-alerts-count');
    if (alertBadge) {
      alertBadge.textContent = alertCount;
      alertBadge.style.display = alertCount > 0 ? 'inline-block' : 'none';
    }

    const appBadge = document.getElementById('nav-approvals-count');
    if (appBadge) {
      appBadge.textContent = pendingTotal;
      appBadge.style.display = pendingTotal > 0 ? 'inline-block' : 'none';
    }

    const repTabCount = document.getElementById('count-tab-replenish');
    if (repTabCount) repTabCount.textContent = m.pending_replenishments || 0;

    const resTabCount = document.getElementById('count-tab-rescue');
    if (resTabCount) resTabCount.textContent = m.pending_expiry_rescues || 0;

    // Update KPI grid in automation view if present
    const elWorkflows = document.getElementById('kpi-auto-workflows');
    const elReplenish = document.getElementById('kpi-pending-replenish');
    const elRescue = document.getElementById('kpi-pending-rescue');
    const elAlerts = document.getElementById('kpi-active-alerts');

    if (elWorkflows && data.workflows) {
      const enabled = data.workflows.filter(w => w.enabled).length;
      elWorkflows.textContent = `${enabled} / ${data.workflows.length}`;
    }
    if (elReplenish) elReplenish.textContent = m.pending_replenishments || 0;
    if (elRescue) elRescue.textContent = m.pending_expiry_rescues || 0;
    if (elAlerts) elAlerts.textContent = alertCount;
  } catch (err) {
    console.warn('[updateGlobalBadges] error:', err);
  }
}

async function loadAutomationStatus() {
  const container = document.getElementById('automation-cards-container');
  if (!container) return;

  try {
    const res = await fetch('/api/automation/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    automationState.workflows = data.workflows || [];

    updateGlobalBadges();
    renderWorkflowCards(automationState.workflows);
  } catch (err) {
    container.innerHTML = `<div class="card" style="padding:1rem;color:#dc2626;">Error loading automation status: ${err.message}</div>`;
  }
}

function renderWorkflowCards(workflows) {
  const container = document.getElementById('automation-cards-container');
  if (!container) return;

  if (!workflows || workflows.length === 0) {
    container.innerHTML = '<div class="card"><p style="padding:1rem">No automation workflows found.</p></div>';
    return;
  }

  container.innerHTML = workflows.map(w => {
    const defaultIcon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>';
    const meta = WORKFLOW_ICONS[w.id] || { icon: defaultIcon, bg: '#f1f5f9', color: '#475569' };
    const isEnabled = w.enabled;
    const statusClass = !isEnabled ? 'status-disabled' :
                        (w.last_status === 'ERROR' ? 'status-error' : 'status-enabled');
    const statusText = !isEnabled ? 'Disabled' :
                       (w.last_status === 'ERROR' ? 'Error' : 'Enabled & Active');

    const intervalMinutes = Math.round((w.interval_seconds || 0) / 60);
    const cadenceLabel = intervalMinutes >= 60 ? `Every ${(intervalMinutes/60).toFixed(1)} hrs` : `Every ${intervalMinutes} mins`;

    const lastRunDisplay = w.last_run_at ? new Date(w.last_run_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : 'Never';
    const nextRunDisplay = w.next_run_at ? new Date(w.next_run_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : 'Scheduled';

    const errorAlertHtml = w.last_error ? `
      <div style="margin-top:.5rem;padding:.4rem .6rem;background:#fee2e2;border:1px solid #fca5a5;border-radius:6px;font-size:.72rem;color:#991b1b;">
        <strong>Error:</strong> ${w.last_error}
      </div>` : '';

    return `
      <div class="workflow-card">
        <div class="wf-header">
          <div class="wf-icon-wrap" style="background:${meta.bg};color:${meta.color}">${meta.icon}</div>
          <div class="wf-info">
            <h3 class="wf-title">${w.name}</h3>
            <p class="wf-desc">${w.description}</p>
          </div>
          <span class="status-pill ${statusClass}">${statusText}</span>
        </div>

        <div class="wf-meta">
          <div class="wf-meta-row">
            <span class="wf-meta-label">Schedule Cadence:</span>
            <span class="wf-meta-val">${cadenceLabel}</span>
          </div>
          <div class="wf-meta-row">
            <span class="wf-meta-label">Last Execution:</span>
            <span class="wf-meta-val">${lastRunDisplay} (${w.last_status || 'IDLE'})</span>
          </div>
          <div class="wf-meta-row">
            <span class="wf-meta-label">Next Scheduled Run:</span>
            <span class="wf-meta-val">${nextRunDisplay}</span>
          </div>
          <div class="wf-meta-row">
            <span class="wf-meta-label">Actions Generated:</span>
            <span class="wf-meta-val" style="color:#2563eb">${w.actions_count || 0}</span>
          </div>
        </div>

        ${errorAlertHtml}

        <div class="wf-controls">
          <label class="dryrun-toggle" title="Dry run evaluates rules without committing DB changes">
            <input type="checkbox" id="dryrun-${w.id}">
            <span>Dry Run</span>
          </label>
          <div class="wf-btn-group">
            <button class="btn btn-outline btn-sm" id="btn-toggle-${w.id}" onclick="toggleWorkflow('${w.id}', ${!isEnabled})">
              ${isEnabled ? 'Disable' : 'Enable'}
            </button>
            <button class="btn btn-primary btn-sm" id="btn-run-${w.id}" onclick="runWorkflow('${w.id}')">
              Run Now
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function runWorkflow(workflowId) {
  const btn = document.getElementById(`btn-run-${workflowId}`);
  const dryRunBox = document.getElementById(`dryrun-${workflowId}`);
  const isDryRun = dryRunBox ? dryRunBox.checked : false;

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Executing…';
  }

  showToast(`Running ${workflowId} (${isDryRun ? 'Dry-Run' : 'Live'})...`, 'info', 'Workflow Triggered');

  try {
    const res = await fetch('/api/automation/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_id: workflowId, dry_run: isDryRun })
    });
    const result = await res.json();

    if (result.success) {
      const modeText = result.dry_run ? 'Dry-Run Finished' : 'Execution Finished';
      showToast(`${result.workflow_name || workflowId}: ${result.actions_generated} action(s) evaluated.`, 'success', modeText);
    } else {
      showToast(result.error || 'Execution encountered an issue', 'error', 'Workflow Error');
    }

    // Refresh UI components
    await loadAutomationStatus();
    await loadAutomationHistory();
    await updateGlobalBadges();
  } catch (err) {
    showToast(err.message, 'error', 'Network Error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Run Now';
    }
  }
}

async function toggleWorkflow(workflowId, targetEnabled) {
  const btn = document.getElementById(`btn-toggle-${workflowId}`);
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/automation/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_id: workflowId, enabled: targetEnabled })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(`${workflowId} is now ${targetEnabled ? 'Enabled' : 'Disabled'}`, 'success', 'Status Updated');
    await loadAutomationStatus();
  } catch (err) {
    showToast(err.message, 'error', 'Update Failed');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadAutomationHistory() {
  const tbody = document.getElementById('automation-history-tbody');
  if (!tbody) return;

  const filterSelect = document.getElementById('history-filter-wf');
  const wfId = filterSelect ? filterSelect.value : '';

  let url = '/api/automation/history?limit=30';
  if (wfId) url += `&workflow_id=${encodeURIComponent(wfId)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    automationState.history = data.history || [];

    if (automationState.history.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No execution logs found. Run a workflow above to generate audit logs.</td></tr>';
      return;
    }

    tbody.innerHTML = automationState.history.map(h => {
      const isDry = Boolean(h.is_dry_run);
      const isSuccess = h.status === 'SUCCESS';
      const statusPill = isSuccess ? 'status-active' : 'status-error';
      const modePill = isDry ? 'status-dryrun' : 'status-disabled';

      const durationSec = ((h.duration_ms || 0) / 1000).toFixed(2);
      const startTime = h.started_at ? new Date(h.started_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : '—';

      return `
        <tr>
          <td><strong>${h.workflow_id}</strong></td>
          <td><span class="chip chip-subtle">${h.trigger_type}</span></td>
          <td><span class="status-pill ${modePill}">${isDry ? 'Dry-Run' : 'Live'}</span></td>
          <td><span class="status-pill ${statusPill}">${h.status}</span></td>
          <td style="font-weight:600;color:#2563eb">${h.actions_generated}</td>
          <td style="font-size:.78rem;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${h.error_message || ''}">
            ${h.error_message ? `<span style="color:#dc2626">${h.error_message}</span>` : '<span style="color:#16a34a">Clean execution</span>'}
          </td>
          <td style="font-size:.8rem;color:#64748b">${startTime}</td>
          <td style="font-size:.8rem">${durationSec}s</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:#dc2626;padding:1rem;">Error loading history: ${err.message}</td></tr>`;
  }
}

/* ══════════════════════════════════════
   MANAGER APPROVAL INBOX
══════════════════════════════════════ */
function switchApprovalTab(tab) {
  const tabRep = document.getElementById('subtab-replenish');
  const tabRes = document.getElementById('subtab-rescue');
  const panelRep = document.getElementById('approvals-replenish-panel');
  const panelRes = document.getElementById('approvals-rescue-panel');

  if (tab === 'replenish') {
    if (tabRep) tabRep.classList.add('active');
    if (tabRes) tabRes.classList.remove('active');
    if (panelRep) panelRep.classList.remove('hidden');
    if (panelRes) panelRes.classList.add('hidden');
    loadReplenishments();
  } else {
    if (tabRep) tabRep.classList.remove('active');
    if (tabRes) tabRes.classList.add('active');
    if (panelRep) panelRep.classList.add('hidden');
    if (panelRes) panelRes.classList.remove('hidden');
    loadExpiryRescue();
  }
}

async function loadApprovals() {
  await loadReplenishments();
  await loadExpiryRescue();
  await updateGlobalBadges();
}

async function loadReplenishments() {
  const tbody = document.getElementById('replenish-tbody');
  if (!tbody) return;

  const statusFilter = document.getElementById('replenish-status-filter');
  const status = statusFilter ? statusFilter.value : 'PENDING_APPROVAL';

  try {
    const res = await fetch(`/api/automation/replenishment?status=${encodeURIComponent(status)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    automationState.replenishments = data.requests || [];

    renderReplenishmentsTable(automationState.replenishments);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="10" style="color:#dc2626;padding:1rem;">Error loading replenishment requests: ${err.message}</td></tr>`;
  }
}

function filterReplenishTable() {
  const query = (document.getElementById('replenish-search').value || '').toLowerCase();
  const filtered = automationState.replenishments.filter(r =>
    (r.store_name || '').toLowerCase().includes(query) ||
    (r.city || '').toLowerCase().includes(query) ||
    (r.product_name || '').toLowerCase().includes(query) ||
    (r.reason || '').toLowerCase().includes(query)
  );
  renderReplenishmentsTable(filtered);
}

function renderReplenishmentsTable(requests) {
  const tbody = document.getElementById('replenish-tbody');
  const countLabel = document.getElementById('replenish-count-label');
  if (!tbody) return;

  if (countLabel) countLabel.textContent = `${requests.length} records shown`;

  if (requests.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" class="loading-row">No replenishment requests match the selected status. Run Auto-Replenishment to scan stores.</td></tr>';
    return;
  }

  tbody.innerHTML = requests.map(r => {
    const isPending = r.status === 'PENDING_APPROVAL';
    const statusClass = r.status === 'APPROVED' ? 'status-active' :
                        (r.status === 'REJECTED' ? 'status-error' : 'status-warning');

    const actionCell = isPending ? `
      <div style="display:flex;gap:.35rem">
        <button class="btn-approve" onclick="handleReplenishAction(${r.id}, 'approve')">Approve PO</button>
        <button class="btn-reject" onclick="handleReplenishAction(${r.id}, 'reject')">Reject</button>
      </div>` : `
      <div class="text-muted-xs">
        <strong>${r.approved_by || 'Manager'}</strong><br>
        ${r.approval_notes ? `<em>"${r.approval_notes}"</em>` : ''}
      </div>`;

    return `
      <tr>
        <td><strong>#${r.id}</strong></td>
        <td><strong>${r.store_name}</strong><br><small style="color:#64748b">${r.city}</small></td>
        <td>${r.product_name}</td>
        <td>
          <span style="color:#dc2626;font-weight:700">${r.current_stock}</span> /
          <span style="color:#64748b">${r.reorder_point} ROP</span>
        </td>
        <td>${r.safety_stock}</td>
        <td style="font-weight:700;color:#2563eb;font-size:.95rem">+${r.suggested_order_qty} units</td>
        <td>${fmtINR(r.estimated_total_cost)}</td>
        <td style="font-size:.78rem;max-width:240px;line-height:1.3">${r.reason}</td>
        <td><span class="status-pill ${statusClass}">${r.status}</span></td>
        <td>${actionCell}</td>
      </tr>
    `;
  }).join('');
}

async function handleReplenishAction(requestId, action) {
  const currentRole = USER_ROLES[state.currentUser] || {};
  const defaultManager = `${currentRole.name || 'Duty Manager'} (${currentRole.badge || 'Admin'})`;

  const isApprove = action === 'approve';
  const dialogResult = await showActionDialog({
    title: isApprove ? 'Approve Replenishment PO' : 'Reject Replenishment Proposal',
    subtitle: `Replenishment Request #${requestId}`,
    message: isApprove ?
      `You are authorizing procurement/dispatch for <strong>Proposal #${requestId}</strong>. An official audit timestamp will be recorded under your name.` :
      `You are rejecting <strong>Proposal #${requestId}</strong>. Please provide a brief justification for the audit log.`,
    inputLabel: isApprove ? 'Approval Notes (Optional):' : 'Rejection Reason (Required):',
    defaultValue: isApprove ? 'Approved for dispatch' : 'Stock surplus available at adjacent hub',
    confirmText: isApprove ? 'Confirm Approval' : 'Confirm Rejection'
  });

  if (!dialogResult.confirmed) return;
  const notes = dialogResult.value;

  try {
    const res = await fetch('/api/automation/replenishment/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: requestId,
        action: action,
        manager_name: defaultManager,
        notes: notes
      })
    });
    const result = await res.json();
    if (result.success) {
      showToast(`Request #${requestId} ${action}d successfully`, 'success', 'Proposal Updated');
      await loadReplenishments();
      await updateGlobalBadges();
    } else {
      showToast(result.error || 'Failed to update request', 'error', 'Action Failed');
    }
  } catch (err) {
    showToast(err.message, 'error', 'Network Error');
  }
}

async function loadExpiryRescue() {
  const tbody = document.getElementById('rescue-tbody');
  if (!tbody) return;

  const statusFilter = document.getElementById('rescue-status-filter');
  const status = statusFilter ? statusFilter.value : 'PENDING_APPROVAL';

  try {
    const res = await fetch(`/api/automation/expiry-rescue?status=${encodeURIComponent(status)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    automationState.expiryTransfers = data.transfers || [];

    renderRescueTable(automationState.expiryTransfers);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="12" style="color:#dc2626;padding:1rem;">Error loading expiry rescues: ${err.message}</td></tr>`;
  }
}

function filterRescueTable() {
  const query = (document.getElementById('rescue-search').value || '').toLowerCase();
  const filtered = automationState.expiryTransfers.filter(r =>
    (r.batch_id || '').toLowerCase().includes(query) ||
    (r.source_warehouse || '').toLowerCase().includes(query) ||
    (r.target_store || '').toLowerCase().includes(query) ||
    (r.product_name || '').toLowerCase().includes(query)
  );
  renderRescueTable(filtered);
}

function renderRescueTable(transfers) {
  const tbody = document.getElementById('rescue-tbody');
  const countLabel = document.getElementById('rescue-count-label');
  if (!tbody) return;

  if (countLabel) countLabel.textContent = `${transfers.length} records shown`;

  if (transfers.length === 0) {
    tbody.innerHTML = '<tr><td colspan="12" class="loading-row">No expiry rescue transfers found. Run Expiry Rescue to scan batches.</td></tr>';
    return;
  }

  tbody.innerHTML = transfers.map(t => {
    const isPending = t.status === 'PENDING_APPROVAL';
    const statusClass = t.status === 'APPROVED' ? 'status-active' :
                        (t.status === 'REJECTED' ? 'status-error' : 'status-warning');

    const marginDays = (t.batch_expiry_days - (t.estimated_transit_hours / 24)).toFixed(1);

    const actionCell = isPending ? `
      <div style="display:flex;gap:.35rem">
        <button class="btn-approve" onclick="handleRescueAction(${t.id}, 'approve')">Authorize</button>
        <button class="btn-reject" onclick="handleRescueAction(${t.id}, 'reject')">Reject</button>
      </div>` : `
      <div class="text-muted-xs">
        <strong>${t.approved_by || 'Manager'}</strong><br>
        ${t.approval_notes ? `<em>"${t.approval_notes}"</em>` : ''}
      </div>`;

    return `
      <tr>
        <td><strong>#${t.id}</strong></td>
        <td><code>${t.batch_id}</code></td>
        <td><strong>${t.product_name}</strong></td>
        <td>${t.source_warehouse}</td>
        <td><span style="color:#16a34a;font-weight:600">${t.target_store}</span></td>
        <td style="color:#dc2626;font-weight:700">${t.batch_expiry_days} days</td>
        <td>${t.estimated_transit_hours} hrs</td>
        <td style="font-weight:700;color:#2563eb">${t.suggested_transfer_qty} units</td>
        <td>${fmtINR(t.inventory_value)}</td>
        <td>
          <span class="chip chip-healthy" title="Remaining life after transit: ${marginDays} days">
            Expiry &gt; Transit + 1.0d
          </span>
        </td>
        <td><span class="status-pill ${statusClass}">${t.status}</span></td>
        <td>${actionCell}</td>
      </tr>
    `;
  }).join('');
}

async function handleRescueAction(transferId, action) {
  const currentRole = USER_ROLES[state.currentUser] || {};
  const defaultManager = `${currentRole.name || 'Warehouse Operations Head'} (${currentRole.badge || 'Admin'})`;

  const isApprove = action === 'approve';
  const dialogResult = await showActionDialog({
    title: isApprove ? 'Authorize FEFO Expiry Rescue' : 'Reject Stock Transfer',
    subtitle: `Rescue Transfer #${transferId}`,
    message: isApprove ?
      `You are authorizing expedited store transfer for <strong>Transfer #${transferId}</strong>. Stock will be dispatched before batch expiration.` :
      `You are rejecting <strong>Transfer #${transferId}</strong>. Please provide a reason for the audit record.`,
    inputLabel: isApprove ? 'Dispatch Notes (Optional):' : 'Rejection Reason (Required):',
    defaultValue: isApprove ? 'Authorized for expedited store transfer' : 'Store shelf capacity constrained',
    confirmText: isApprove ? 'Authorize Transfer' : 'Reject Transfer'
  });

  if (!dialogResult.confirmed) return;
  const notes = dialogResult.value;

  try {
    const res = await fetch('/api/automation/expiry-rescue/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transfer_id: transferId,
        action: action,
        manager_name: defaultManager,
        notes: notes
      })
    });
    const result = await res.json();
    if (result.success) {
      showToast(`Expiry transfer #${transferId} ${action}d successfully`, 'success', 'Transfer Updated');
      await loadExpiryRescue();
      await updateGlobalBadges();
    } else {
      showToast(result.error || 'Failed to update transfer', 'error', 'Action Failed');
    }
  } catch (err) {
    showToast(err.message, 'error', 'Network Error');
  }
}

/* ══════════════════════════════════════
   AUTOMATED ALERT CENTER
══════════════════════════════════════ */
async function loadAlerts() {
  const tbody = document.getElementById('alerts-tbody');
  if (!tbody) return;

  const sevFilter = document.getElementById('alert-severity-filter');
  const statFilter = document.getElementById('alert-status-filter');
  const typeFilter = document.getElementById('alert-type-filter');

  const severity = sevFilter ? sevFilter.value : 'all';
  const status = statFilter ? statFilter.value : '';
  const alertType = typeFilter ? typeFilter.value : 'all';

  let url = `/api/automation/alerts?severity=${encodeURIComponent(severity)}&status=${encodeURIComponent(status)}&type=${encodeURIComponent(alertType)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    automationState.alerts = data.alerts || [];

    // Update counters
    const counts = data.counts || {};
    const elCrit = document.getElementById('alert-stat-critical');
    const elWarn = document.getElementById('alert-stat-warning');
    const elTot  = document.getElementById('alert-stat-total');

    if (elCrit) elCrit.textContent = counts.critical || 0;
    if (elWarn) elWarn.textContent = counts.warning || 0;
    if (elTot)  elTot.textContent = counts.total_open || 0;

    updateGlobalBadges();
    renderAlertsTable(automationState.alerts);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:#dc2626;padding:1rem;">Error loading alerts: ${err.message}</td></tr>`;
  }
}

function setAlertSeverityFilter(sev) {
  const dropdown = document.getElementById('alert-severity-filter');
  if (dropdown) dropdown.value = sev;
  loadAlerts();
}

function filterAlertTable() {
  const query = (document.getElementById('alert-search').value || '').toLowerCase();
  const filtered = automationState.alerts.filter(a =>
    (a.message || '').toLowerCase().includes(query) ||
    (a.entity_id || '').toLowerCase().includes(query) ||
    (a.alert_type || '').toLowerCase().includes(query) ||
    (a.recommended_action || '').toLowerCase().includes(query)
  );
  renderAlertsTable(filtered);
}

function renderAlertsTable(alerts) {
  const tbody = document.getElementById('alerts-tbody');
  const countLabel = document.getElementById('alert-count-label');
  if (!tbody) return;

  if (countLabel) countLabel.textContent = `${alerts.length} alerts displayed`;

  if (alerts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No alerts found matching the active criteria. The supply network is healthy.</td></tr>';
    return;
  }

  tbody.innerHTML = alerts.map(a => {
    const sevPill = a.severity === 'CRITICAL' ? 'status-critical' :
                    (a.severity === 'WARNING' ? 'status-warning' : 'status-disabled');

    const statusPill = a.status === 'RESOLVED' ? 'status-active' :
                       (a.status === 'ACKNOWLEDGED' ? 'status-warning' : 'status-critical');

    const timeFormatted = a.created_at ? new Date(a.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : '—';

    let actionBtns = '';
    if (a.status === 'OPEN') {
      actionBtns = `
        <div style="display:flex;gap:.3rem">
          <button class="btn-acknowledge" onclick="handleAlertAction(${a.id}, 'acknowledge')">Ack</button>
          <button class="btn-resolve" onclick="handleAlertAction(${a.id}, 'resolve')">Resolve</button>
        </div>`;
    } else if (a.status === 'ACKNOWLEDGED') {
      actionBtns = `
        <button class="btn-resolve" onclick="handleAlertAction(${a.id}, 'resolve')">Resolve</button>
        <span class="text-muted-xs" style="display:block;margin-top:.2rem">by ${a.acknowledged_by || 'Staff'}</span>`;
    } else {
      actionBtns = `<span class="text-muted-xs">Resolved by ${a.resolved_by || 'Staff'}</span>`;
    }

    return `
      <tr>
        <td><span class="status-pill ${sevPill}">${a.severity}</span></td>
        <td><span class="chip chip-subtle">${a.alert_type}</span></td>
        <td><code>${a.entity_id || 'System'}</code></td>
        <td style="font-size:.82rem;font-weight:500;line-height:1.35;max-width:280px">${a.message}</td>
        <td style="font-size:.8rem;color:#2563eb;font-weight:600;max-width:240px">${a.recommended_action || '—'}</td>
        <td style="font-size:.78rem;color:#64748b">${timeFormatted}</td>
        <td><span class="status-pill ${statusPill}">${a.status}</span></td>
        <td>${actionBtns}</td>
      </tr>
    `;
  }).join('');
}

async function handleAlertAction(alertId, action) {
  const currentRole = USER_ROLES[state.currentUser] || {};
  const userName = currentRole.name || 'Duty Operations Manager';

  try {
    const res = await fetch('/api/automation/alerts/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_id: alertId, action: action, user_name: userName })
    });
    const result = await res.json();
    if (result.success) {
      showToast(`Alert #${alertId} marked as ${action === 'acknowledge' ? 'Acknowledged' : 'Resolved'}`, 'success', 'Alert Updated');
      await loadAlerts();
    } else {
      showToast(result.error || 'Failed to update alert', 'error', 'Update Error');
    }
  } catch (err) {
    showToast(err.message, 'error', 'Network Error');
  }
}

/* ══════════════════════════════════════
   DISTRIBUTION OPTIMIZATION OPTIONS
══════════════════════════════════════ */
async function loadDistributionOptions() {
  const tbody = document.getElementById('ranked-dist-tbody');
  if (!tbody) return;

  try {
    const res = await fetch('/api/automation/distribution-options');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rows = data.recommendations || [];

    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="loading-row">No active distribution options. Run Distribution Optimization workflow to compute rankings.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(r => {
      const isRank1 = r.warehouse_rank === 1;
      const rankBadge = isRank1 ? '<span class="chip chip-healthy">Rank 1 (Optimal)</span>' :
                                  `<span class="chip chip-subtle">Rank ${r.warehouse_rank}</span>`;
      const rowStyle = isRank1 ? 'style="background:#f8fafc;font-weight:500"' : '';

      return `
        <tr ${rowStyle}>
          <td><strong>${r.store_name}</strong></td>
          <td>${r.product_name}</td>
          <td style="color:#dc2626;font-weight:600">${r.deficit_units} units</td>
          <td>${rankBadge}</td>
          <td><strong>${r.candidate_warehouse}</strong></td>
          <td>${r.distance_km} km</td>
          <td>${fmtINR(r.estimated_freight_cost)}</td>
          <td>${r.transit_time_hours} hrs</td>
          <td style="color:#16a34a;font-weight:600">${r.available_units} units</td>
          <td style="font-size:.78rem;color:#475569">${r.rationale}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="10" style="color:#dc2626;padding:1rem;">Error loading distribution options: ${err.message}</td></tr>`;
  }
}

/* ══════════════════════════════════════
   DELIVERY MONITORING (MANIFEST CHECKPOINTS)
══════════════════════════════════════ */
async function loadDeliveryMonitoring() {
  const tbody = document.getElementById('delivery-monitor-tbody');
  if (!tbody) return;

  try {
    const res = await fetch('/api/automation/deliveries');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const shipments = data.shipments || [];

    if (shipments.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="loading-row">No active delivery shipments tracked.</td></tr>';
      return;
    }

    tbody.innerHTML = shipments.map(s => {
      const isDelayed = s.status === 'DELAYED';
      const statusPill = isDelayed ? 'status-critical' :
                         (s.status === 'DELIVERED' ? 'status-active' : 'status-warning');

      const delayMinutes = s.delay_minutes || 0;
      const delayCell = delayMinutes > 0 ?
        `<span style="color:#dc2626;font-weight:700">+${delayMinutes} mins overdue</span>` :
        '<span style="color:#16a34a">On Time (0 mins)</span>';

      const expDate = s.expected_delivery_at ? new Date(s.expected_delivery_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '—';
      const dispDate = s.dispatched_at ? new Date(s.dispatched_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '—';

      return `
        <tr ${isDelayed ? 'style="background:#fef2f2"' : ''}>
          <td><strong>${s.shipment_code || s.shipment_id || ('SHP-' + s.id)}</strong></td>
          <td>${s.origin_warehouse_id || s.source_warehouse} → <strong>${s.destination_city || s.destination_store}</strong></td>
          <td><strong>${s.assigned_driver || s.driver_name}</strong><br><small style="color:#64748b">${s.vehicle_no || s.vehicle_number}</small></td>
          <td>${dispDate}</td>
          <td>${expDate}</td>
          <td>${s.actual_delivery_at ? new Date(s.actual_delivery_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : 'In Transit'}</td>
          <td>${delayCell}</td>
          <td><span class="status-pill ${statusPill}">${s.status}</span></td>
          <td>
            ${isDelayed ? `<span class="chip chip-warning" title="${s.delay_reason || ''}">Delay Alert: ${s.delay_reason || 'Delayed'}</span>` : '<span class="chip chip-subtle">SLA Compliant</span>'}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" style="color:#dc2626;padding:1rem;">Error loading deliveries: ${err.message}</td></tr>`;
  }
}

/* ══════════════════════════════════════
   INIT
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  let authenticatedRole = null;
  try {
    authenticatedRole = sessionStorage.getItem('optistock_auth_role');
  } catch(e) {}

  if (authenticatedRole && USER_ROLES[authenticatedRole]) {
    applyUserRole(authenticatedRole);
  } else {
    // Start with Admin selected but open PIN authentication prompt
    applyUserRole('admin');
    promptPinForRole('admin');
  }

  // Initial badge update and periodic polling
  updateGlobalBadges();
  setInterval(updateGlobalBadges, 30000);
});
