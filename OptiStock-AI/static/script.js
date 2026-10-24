let demandChart = null;
let healthChart = null;
let forecastChart = null;
let currentPlan = null;
let inventoryRows = [];
let toastTimer = null;

const money = value => "₹" + Number(value || 0).toLocaleString("en-IN", {maximumFractionDigits: 2});
const number = value => Number(value || 0).toLocaleString("en-IN");
const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("Could not load data");
  return response.json();
}
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}
function navigate(section) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.section === section));
  document.querySelectorAll(".section-view").forEach(s => s.classList.toggle("active", s.id === `${section}-section`));
  const titles = {
    overview: ["Distribution overview", "A clearer view of inventory, demand and delivery decisions."],
    distribution: ["Distribution plan", "Recommended allocations based on demand, availability and transport cost."],
    inventory: ["Inventory control tower", "Track availability, product shelf life and potential wastage."],
    forecast: ["Demand forecast", "A planning signal built from illustrative historical demand."]
  };
  document.getElementById("page-title").textContent = titles[section][0];
  document.getElementById("page-subtitle").textContent = titles[section][1];
  if (section === "distribution") loadPlan();
  if (section === "inventory") loadInventory();
  if (section === "forecast") loadForecast();
}
document.querySelectorAll(".nav-item").forEach(b => b.addEventListener("click", () => navigate(b.dataset.section)));
document.querySelectorAll("[data-goto]").forEach(b => b.addEventListener("click", () => navigate(b.dataset.goto)));

async function loadSummary() {
  const data = await getJSON("/api/summary");
  document.getElementById("total-inventory").textContent = number(data.total_inventory);
  document.getElementById("stockout-risk").textContent = number(data.stockout_locations);
  document.getElementById("shipment-count").textContent = number(data.shipment_count);
  document.getElementById("transport-cost").textContent = money(data.transport_cost);
  document.getElementById("estimated-savings").textContent = money(data.estimated_savings);
  document.getElementById("baseline-cost").textContent = money(data.baseline_cost);
  document.getElementById("plan-cost").textContent = money(data.transport_cost);
  const ratio = data.baseline_cost ? Math.min(100, data.transport_cost / data.baseline_cost * 100) : 0;
  document.getElementById("compare-fill").style.width = `${ratio}%`;
}
async function loadInventory() {
  inventoryRows = await getJSON("/api/inventory");
  renderInventory();
  const healthy = inventoryRows.filter(x => x.status === "Healthy").length;
  const expiring = inventoryRows.filter(x => x.status === "Expiring soon").length;
  const urgent = inventoryRows.filter(x => x.status === "Urgent").length;
  document.getElementById("healthy-count").textContent = healthy;
  document.getElementById("expiring-count").textContent = expiring;
  document.getElementById("urgent-count").textContent = urgent;
  const ctx = document.getElementById("healthChart");
  if (healthChart) healthChart.destroy();
  healthChart = new Chart(ctx, {
    type: "doughnut",
    data: {labels:["Healthy stock","Expiring soon","Urgent"], datasets:[{data:[healthy,expiring,urgent],backgroundColor:["#a3e635","#ffb36b","#ff7777"],borderColor:"#121823",borderWidth:4,hoverOffset:5}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:"72%",plugins:{legend:{display:false}}}
  });
}
function renderInventory() {
  const query = (document.getElementById("inventory-search")?.value || "").toLowerCase();
  const status = document.getElementById("inventory-status")?.value || "all";
  const rows = inventoryRows.filter(x => `${x.product} ${x.warehouse} ${x.city} ${x.category}`.toLowerCase().includes(query) && (status === "all" || x.status === status));
  document.getElementById("inventory-record-count").textContent = `${rows.length} RECORDS`;
  document.getElementById("inventory-table").innerHTML = rows.length ? rows.map(x => `
    <tr><td class="product-cell">${esc(x.product)}</td><td>${esc(x.category)}</td><td>${esc(x.warehouse)}<div class="muted-small">${esc(x.city)}</div></td><td class="qty-cell">${number(x.quantity)}</td><td>${x.expiry_days} days</td><td><span class="status-chip ${x.status.replaceAll(" ","-")}">${esc(x.status)}</span></td></tr>`).join("") : `<tr><td colspan="6" class="empty-row">No inventory matches your filters.</td></tr>`;
}
document.getElementById("inventory-search").addEventListener("input", renderInventory);
document.getElementById("inventory-status").addEventListener("change", renderInventory);

async function loadPlan() {
  const days = document.getElementById("horizon").value;
  const plan = await getJSON(`/api/plan?days=${encodeURIComponent(days)}`);
  currentPlan = plan;
  document.getElementById("units-shipped").textContent = number(plan.units_shipped);
  document.getElementById("unmet-demand").textContent = number(plan.total_unmet);
  document.getElementById("expiry-count").textContent = number(plan.expiry_alerts.length);
  document.getElementById("plan-caption").textContent = `${plan.shipments.length} allocation lines · ${plan.horizon_days}-day planning horizon · simulated data`;
  document.getElementById("shipment-table").innerHTML = plan.shipments.length ? plan.shipments.map(x => `
    <tr><td class="product-cell">${esc(x.product)}</td><td>${esc(x.warehouse)}<div class="muted-small">${esc(x.warehouse_id)}</div></td><td>${esc(x.store)}<div class="muted-small">${esc(x.city)}</div></td><td class="qty-cell">${number(x.quantity)}</td><td class="cost-cell">${money(x.transport_cost)}</td><td class="reason-cell">${esc(x.reason)}</td></tr>`).join("") : `<tr><td colspan="6" class="empty-row">No shipments recommended.</td></tr>`;
  document.getElementById("unmet-table").innerHTML = plan.unmet.length ? plan.unmet.map(x => `
    <tr><td class="product-cell">${esc(x.product)}</td><td>${esc(x.store)}</td><td>${esc(x.city)}</td><td><span class="status-chip Urgent">${number(x.unmet_quantity)}</span></td></tr>`).join("") : `<tr><td colspan="4" class="empty-row">All estimated demand was covered for this horizon.</td></tr>`;
  renderPriority(plan.expiry_alerts);
}
function renderPriority(alerts) {
  const list = document.getElementById("priority-list");
  const items = alerts.slice().sort((a,b)=>a.expiry_days-b.expiry_days).slice(0,4);
  list.innerHTML = items.length ? items.map(x => `<div class="priority-item"><div class="priority-symbol">!</div><div class="priority-copy"><strong>${esc(x.product)}</strong><span>${esc(x.warehouse)} · ${number(x.quantity)} units · expires in ${x.expiry_days} days</span></div><span class="priority-tag">${x.expiry_days <= 3 ? "URGENT" : "WATCH"}</span></div>`).join("") : `<div class="loading">No expiry alerts.</div>`;
}
document.getElementById("refresh-plan").addEventListener("click", async () => { await loadPlan(); await loadSummary(); showToast("Distribution plan recalculated"); });
document.getElementById("generate-btn").addEventListener("click", async () => {
  navigate("distribution");
  await loadPlan();
  showToast("Fresh distribution plan generated");
});
document.getElementById("download-csv").addEventListener("click", () => {
  if (!currentPlan || !currentPlan.shipments.length) { showToast("No shipment rows to export"); return; }
  const columns = ["product","warehouse","store","city","quantity","transport_cost","expiry_days","reason"];
  const csvCell = value => `"${String(value ?? "").replaceAll('"','""')}"`;
  const csv = [columns.join(","), ...currentPlan.shipments.map(row => columns.map(c => csvCell(row[c])).join(","))].join("\r\n");
  const blob = new Blob([csv], {type:"text/csv;charset=utf-8;"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "optistock_distribution_plan.csv";
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("CSV export downloaded");
});
async function loadForecast() {
  const data = await getJSON("/api/forecast");
  document.getElementById("forecast-method").textContent = data.method;
  const ctx = document.getElementById("forecastChart");
  if (forecastChart) forecastChart.destroy();
  forecastChart = new Chart(ctx, {
    type:"line",
    data:{labels:[...data.history_labels,...data.forecast_labels],datasets:[
      {label:"Simulated historical demand",data:[...data.history,...Array(7).fill(null)],borderColor:"#68b9ff",backgroundColor:"#68b9ff22",fill:true,tension:.35,pointRadius:3},
      {label:"Illustrative forecast",data:[...Array(6).fill(null),data.history[data.history.length-1],...data.forecast],borderColor:"#a3e635",backgroundColor:"#a3e63516",fill:true,tension:.35,borderDash:[5,4],pointRadius:3}
    ]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:"index",intersect:false},plugins:{legend:{labels:{color:"#aab5c5",usePointStyle:true,boxWidth:7,font:{size:10}}}},scales:{x:{ticks:{color:"#7e8b9e",font:{size:9}},grid:{color:"#202a37"}},y:{beginAtZero:true,ticks:{color:"#7e8b9e",font:{size:9}},grid:{color:"#202a37"}}}}
  });
}
async function loadDemandChart() {
  const data = await getJSON("/api/forecast");
  const ctx = document.getElementById("demandChart");
  if (demandChart) demandChart.destroy();
  demandChart = new Chart(ctx, {
    type:"line",
    data:{labels:[...data.history_labels,...data.forecast_labels.slice(0,3)],datasets:[
      {label:"Simulated history",data:[...data.history,...Array(3).fill(null)],borderColor:"#68b9ff",backgroundColor:"#68b9ff17",fill:true,tension:.35,pointRadius:2,borderWidth:2},
      {label:"Forecast",data:[...Array(6).fill(null),data.history[6],...data.forecast.slice(0,3)],borderColor:"#a3e635",backgroundColor:"#a3e63512",fill:false,tension:.35,pointRadius:3,borderDash:[4,4],borderWidth:2}
    ]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:"#7e8b9e",font:{size:9}},grid:{display:false}},y:{beginAtZero:true,ticks:{color:"#7e8b9e",font:{size:9}},grid:{color:"#202a37"}}}}
  });
}
(async function init() {
  try {
    await Promise.all([loadSummary(), loadInventory(), loadDemandChart()]);
    await loadPlan();
  } catch (error) {
    console.error(error);
    showToast("Could not load app data. Check that Flask is running.");
  }
})();
