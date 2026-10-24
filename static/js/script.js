/**
 * OptiStock AI — Smart Inventory & Warehouse Management System
 * Frontend Scripts: Modals, Sidebar, Password Toggles & Chart.js Visualizations
 */

document.addEventListener('DOMContentLoaded', () => {
  // Mobile Sidebar Drawer Toggle
  const sidebarToggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('appSidebar');

  if (sidebarToggleBtn && sidebar) {
    sidebarToggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (
        window.innerWidth <= 860 &&
        sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        !sidebarToggleBtn.contains(e.target)
      ) {
        sidebar.classList.remove('open');
      }
    });
  }

  // Close modals on clicking outside or ESC key
  document.querySelectorAll('.modal-backdrop').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('open');
      }
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
    }
  });
});

/**
 * Modal Dialog Open and Close Handlers
 */
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('open');
    const firstInput = modal.querySelector('input, select, textarea');
    if (firstInput) firstInput.focus();
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('open');
  }
}

/**
 * Toggle Password Visibility for Login & Registration
 */
function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;

  const eyeOpen = btn.querySelector('.eye-open');
  const eyeClosed = btn.querySelector('.eye-closed');

  if (input.type === 'password') {
    input.type = 'text';
    if (eyeOpen) eyeOpen.style.display = 'none';
    if (eyeClosed) eyeClosed.style.display = 'inline-block';
  } else {
    input.type = 'password';
    if (eyeOpen) eyeOpen.style.display = 'inline-block';
    if (eyeClosed) eyeClosed.style.display = 'none';
  }
}

/**
 * Notification Toggle Notification Drawer / Toast
 */
function toggleNotifications() {
  openModal('settingsModal');
}

/**
 * Global Topbar Search Handler
 */
function handleGlobalSearch(query) {
  const analyticsInput = document.getElementById('analyticsSearchInput');
  if (analyticsInput) {
    analyticsInput.value = query;
    filterAnalyticsTable();
  }
}

/**
 * Live Table Filter for Inventory Analytics Table
 */
function filterAnalyticsTable() {
  const searchInput = document.getElementById('analyticsSearchInput');
  const statusFilter = document.getElementById('analyticsStatusFilter');
  const tableBody = document.getElementById('analyticsTableBody');

  if (!tableBody) return;

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const selectedStatus = (statusFilter ? statusFilter.value : '').trim();

  const rows = tableBody.querySelectorAll('tr[data-status]');
  let visibleCount = 0;

  rows.forEach(row => {
    const rowStatus = row.getAttribute('data-status') || '';
    const rowSearch = row.getAttribute('data-search') || '';

    const matchesStatus = !selectedStatus || rowStatus.toLowerCase() === selectedStatus.toLowerCase();
    const matchesSearch = !query || rowSearch.includes(query);

    if (matchesStatus && matchesSearch) {
      row.style.display = '';
      visibleCount++;
    } else {
      row.style.display = 'none';
    }
  });

  const emptyRow = document.getElementById('emptyTableRow');
  if (emptyRow) {
    emptyRow.style.display = visibleCount === 0 ? '' : 'none';
  }
}

/**
 * Cached Chart Data & Inventory Overview Chart Instance
 */
window.optiChartData = null;
window.inventoryOverviewChartInstance = null;

/**
 * Initialize Clean Rounded Bar Chart on Inventory Overview
 */
async function initInventoryOverviewChart() {
  const canvas = document.getElementById('inventoryOverviewChart');
  if (!canvas) return;

  try {
    const res = await fetch('/api/chart-data');
    if (!res.ok) throw new Error('Failed to fetch chart data');
    const data = await res.json();
    window.optiChartData = data;

    Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
    Chart.defaults.color = '#64748b';

    // Default to 'week' period
    const defaultPeriod = 'week';
    const series = (data.time_series && data.time_series[defaultPeriod]) ? data.time_series[defaultPeriod] : {
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      warehouses: [3200, 3400, 3100, 3600, 3800, 3500, 3400],
      retail: [1200, 1450, 1600, 1800, 2100, 2400, 1900]
    };

    const ctx = canvas.getContext('2d');
    if (window.inventoryOverviewChartInstance) {
      window.inventoryOverviewChartInstance.destroy();
    }

    window.inventoryOverviewChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: series.labels,
        datasets: [
          {
            label: 'Warehouses',
            data: series.warehouses,
            backgroundColor: '#8b5cf6', // Soft purple
            hoverBackgroundColor: '#7c3aed',
            borderRadius: 8,
            borderSkipped: false,
            barPercentage: 0.65,
            categoryPercentage: 0.75,
          },
          {
            label: 'Retail Stores',
            data: series.retail,
            backgroundColor: '#3b82f6', // Clean blue
            hoverBackgroundColor: '#2563eb',
            borderRadius: 8,
            borderSkipped: false,
            barPercentage: 0.65,
            categoryPercentage: 0.75,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false,
        },
        plugins: {
          legend: {
            position: 'top',
            align: 'end',
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
              pointStyle: 'circle',
              color: '#475569',
              font: {
                size: 12,
                weight: '600'
              },
              padding: 16
            }
          },
          tooltip: {
            backgroundColor: '#0f172a',
            titleColor: '#ffffff',
            bodyColor: '#e2e8f0',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            padding: 12,
            cornerRadius: 10,
            callbacks: {
              label: function(ctx) {
                const val = ctx.raw || 0;
                return `  ${ctx.dataset.label}: ${val.toLocaleString('en-IN')} units`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: {
              display: false,
              drawBorder: false,
            },
            ticks: {
              color: '#64748b',
              font: {
                size: 11,
                weight: '500'
              }
            }
          },
          y: {
            grid: {
              color: 'rgba(226, 232, 240, 0.6)',
              drawBorder: false,
            },
            ticks: {
              color: '#94a3b8',
              font: {
                size: 11
              },
              callback: function(val) {
                return val >= 1000 ? (val / 1000) + 'k' : val;
              }
            }
          }
        }
      }
    });
  } catch (err) {
    console.error('Failed to load inventory overview chart:', err);
  }
}

/**
 * Switch Inventory Overview Chart Time Range (Day, Week, Month, Year)
 */
function switchInventoryOverviewPeriod(period) {
  // Update UI tab button active state
  document.querySelectorAll('.period-tab-btn').forEach(btn => {
    if (btn.getAttribute('data-period') === period) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  if (!window.inventoryOverviewChartInstance || !window.optiChartData) return;

  const series = window.optiChartData.time_series && window.optiChartData.time_series[period];
  if (!series) return;

  window.inventoryOverviewChartInstance.data.labels = series.labels;
  window.inventoryOverviewChartInstance.data.datasets[0].data = series.warehouses;
  window.inventoryOverviewChartInstance.data.datasets[1].data = series.retail;
  window.inventoryOverviewChartInstance.update();
}

/**
 * Legacy Support for Reports & Previous Dashboard Charts
 */
async function initDashboardCharts() {
  if (document.getElementById('inventoryOverviewChart')) {
    initInventoryOverviewChart();
  }
}
