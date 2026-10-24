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
 * Initialize Dashboard Chart.js Charts
 */
async function initDashboardCharts() {
  const catCanvas = document.getElementById('categoryChart');
  const statusCanvas = document.getElementById('statusChart');

  if (!catCanvas || !statusCanvas) return;

  try {
    const res = await fetch('/api/chart-data');
    if (!res.ok) throw new Error('Failed to fetch chart data');
    const data = await res.json();

    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(13, 19, 34, 0.95)';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.15)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;

    // 1. Category Distribution Chart (Doughnut)
    if (catCanvas && data.categories.labels.length) {
      new Chart(catCanvas, {
        type: 'doughnut',
        data: {
          labels: data.categories.labels,
          datasets: [
            {
              data: data.categories.values,
              backgroundColor: [
                '#3b82f6',
                '#8b5cf6',
                '#06b6d4',
                '#10b981',
                '#f59e0b',
                '#ec4899',
                '#6366f1',
              ],
              borderColor: '#0b1120',
              borderWidth: 2,
              hoverOffset: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: {
                boxWidth: 10,
                color: '#cbd5e1',
                font: { size: 11 },
              },
            },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  const val = ctx.raw || 0;
                  return ` ${ctx.label}: ₹${val.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
                },
              },
            },
          },
        },
      });
    }

    // 2. Stock Health Overview (Doughnut)
    if (statusCanvas && data.status.labels.length) {
      new Chart(statusCanvas, {
        type: 'doughnut',
        data: {
          labels: data.status.labels,
          datasets: [
            {
              data: data.status.counts,
              backgroundColor: [
                'rgba(16, 185, 129, 0.85)', // Healthy
                'rgba(245, 158, 11, 0.85)', // Low Stock
                'rgba(239, 68, 68, 0.85)',  // Critical
              ],
              borderColor: '#0b1120',
              borderWidth: 3,
              hoverOffset: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '70%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                boxWidth: 10,
                usePointStyle: true,
                color: '#cbd5e1',
              },
            },
          },
        },
      });
    }
  } catch (err) {
    console.error('Failed to load chart data:', err);
  }
}
