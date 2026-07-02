/**
 * Dashboard Page — Matrices, Charts per Segmen, Comparison
 */

document.addEventListener('DOMContentLoaded', function() {
  console.log('Dashboard initialized');
  initHeatmaps();
  loadTrafficCharts();
  loadModelComparison();
});

// ── Heatmap Matrices ────────────────────────
function initHeatmaps() {
  var data = window.DASHBOARD_DATA;
  if (!data || !data.rollingMatrices) return;

  data.rollingMatrices.forEach(function(md) {
    var table = document.getElementById('rm-' + md.step);
    if (!table) return;

    var cells = table.querySelectorAll('td.matrix-cell');
    var vals = [];
    
    cells.forEach(function(c) {
      var v = parseFloat(c.getAttribute('data-value'));
      if (!isNaN(v)) vals.push(v);
    });

    if (vals.length === 0) return;

    var mn = Math.min.apply(null, vals);
    var mx = Math.max.apply(null, vals);
    var rng = mx - mn;

    cells.forEach(function(c) {
      var v = parseFloat(c.getAttribute('data-value'));
      if (isNaN(v)) return;
      
      var p = rng ? (v - mn) / rng : 0;
      
      if (p < 0.25) {
        c.classList.add('heat-low');
      } else if (p < 0.5) {
        c.classList.add('heat-mid');
      } else if (p < 0.75) {
        c.classList.add('heat-high');
      } else {
        c.classList.add('heat-xhigh');
      }
    });
  });
}

// ── Traffic Charts per Segmen ───────────────
async function loadTrafficCharts() {
  var data = window.DASHBOARD_DATA;
  if (!data || !data.itinerary || data.itinerary.length === 0) {
    console.warn('No itinerary data for charts');
    return;
  }

  var vehicle = data.vehicleType || 'mobil';
  var isWeekend = data.isWeekend || 0;
  var pairThresholds = data.pairThresholds || {};

  var segments = [];
  var itinerary = data.itinerary;
  
  for (var i = 0; i < itinerary.length; i++) {
    var step = itinerary[i];
    if (!step.is_google_maps && !step.is_depot_arrival && step.from_id && step.to_id) {
      segments.push({
        fromId: step.from_id,
        toId: step.to_id,
        fromName: step.from_name || '',
        toName: step.to_name || '',
        departure: step.departure || '00:00',
        travelTime: step.travel_time || 0
      });
    }
  }

  console.log('Loading ' + segments.length + ' segment charts');

  for (var s = 0; s < segments.length; s++) {
    var seg = segments[s];
    var canvasId = 'chartSegment' + seg.fromId + '_' + seg.toId;
    await renderPairChart(canvasId, seg, vehicle, isWeekend, pairThresholds);
  }
}

async function renderPairChart(canvasId, seg, vehicle, isWeekend, pairThresholds) {
  var canvas = document.getElementById(canvasId);
  if (!canvas) {
    console.warn('Canvas not found: ' + canvasId);
    return;
  }

  try {
    var url = '/api/traffic/pair_pattern?vehicle=' + vehicle +
              '&is_weekend=' + isWeekend +
              '&from_id=' + seg.fromId +
              '&to_id=' + seg.toId;

    var response = await fetch(url);
    if (!response.ok) {
      console.warn('API not ok for ' + canvasId);
      return;
    }

    var chartData = await response.json();
    if (!chartData || !chartData.length) {
      console.warn('No data for ' + canvasId);
      return;
    }

    var labels = [];
    var means = [];
    var mins = [];
    var maxs = [];
    var jamH = [];

    chartData.forEach(function(d) {
      labels.push(d.jam_label || '');
      means.push(d.mean || 0);
      mins.push(d.min || 0);
      maxs.push(d.max || 0);
      jamH.push(d.jam_h || 0);
    });

    // Threshold dari pair_thresholds
    var key = Math.min(seg.fromId, seg.toId) + '_' + Math.max(seg.fromId, seg.toId) + '_' + isWeekend;
    var thr = pairThresholds[key] || { p25: 16, mean: 22, p75: 28 };
    var p25 = thr.p25 || 16;
    var mean = thr.mean || 22;
    var p75 = thr.p75 || 28;

    // Warna titik berdasarkan kategori threshold
    var pointColors = means.map(function(v) {
      if (v <= p25) return '#15803d';
      if (v <= mean) return '#854d0e';
      if (v <= p75) return '#c2410c';
      return '#b91c1c';
    });

    // Hitung posisi jam keberangkatan
    var depParts = seg.departure.split(':');
    var depHourFloat = parseInt(depParts[0]) + parseInt(depParts[1]) / 60;

    var travelTime = seg.travelTime;

    // Tentukan status kemacetan
    var congStatus, congColor;
    if (travelTime <= p25) {
      congStatus = 'Lancar';
      congColor = '#15803d';
    } else if (travelTime <= mean) {
      congStatus = 'Sedang';
      congColor = '#854d0e';
    } else if (travelTime <= p75) {
      congStatus = 'Padat';
      congColor = '#c2410c';
    } else {
      congStatus = 'Macet';
      congColor = '#b91c1c';
    }

    // Cari index slot sebelum dan sesudah
    var slotBeforeIdx = -1;
    var slotAfterIdx = -1;
    for (var i = 0; i < jamH.length - 1; i++) {
      if (depHourFloat >= jamH[i] && depHourFloat <= jamH[i + 1]) {
        slotBeforeIdx = i;
        slotAfterIdx = i + 1;
        break;
      }
    }
    if (slotBeforeIdx === -1) {
      if (depHourFloat <= jamH[0]) {
        slotBeforeIdx = 0;
        slotAfterIdx = 0;
      } else {
        slotBeforeIdx = jamH.length - 1;
        slotAfterIdx = jamH.length - 1;
      }
    }

    // Destroy existing chart
    var existing = Chart.getChart(canvas);
    if (existing) existing.destroy();

    // ── LINE CHART ──
    var chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Rata-rata (menit)',
            data: means,
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.08)',
            borderWidth: 2.5,
            pointRadius: 6,
            pointHoverRadius: 9,
            pointBackgroundColor: pointColors,
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2.5,
            tension: 0.4,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        layout: {
          padding: {
            right: 120
          }
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: 'white',
            titleColor: '#111827',
            bodyColor: '#374151',
            borderColor: '#e5e7eb',
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: function(context) {
                return 'Rata-rata: ' + context.parsed.y.toFixed(1) + ' menit';
              },
              afterBody: function(items) {
                if (!items || items.length === 0) return [];
                var idx = items[0].dataIndex;
                var v = means[idx];
                var label = labels[idx];
                var status, icon;
                if (v <= p25) { status = 'Lancar'; icon = '🟢'; }
                else if (v <= mean) { status = 'Sedang'; icon = '🟡'; }
                else if (v <= p75) { status = 'Padat'; icon = '🟠'; }
                else { status = 'Macet'; icon = '🔴'; }
                return [
                  '',
                  icon + ' ' + status + ' pada ' + label,
                  'Min: ' + mins[idx].toFixed(1) + ' mnt | Maks: ' + maxs[idx].toFixed(1) + ' mnt',
                  '---',
                  'Threshold: P25=' + p25.toFixed(2) + ' | Mean=' + mean.toFixed(2) + ' | P75=' + p75.toFixed(2)
                ];
              }
            }
          }
        },
        scales: {
          y: {
            title: { display: true, text: 'Menit', font: { size: 11, weight: '600' } },
            grid: { color: 'rgba(0,0,0,0.06)' },
            beginAtZero: false
          },
          x: {
            title: { display: true, text: 'Slot 3 Jam', font: { size: 11, weight: '600' } },
            grid: { display: false }
          }
        }
      }
    });

    // ── Custom plugin ──
    var origDraw = chart.draw;
    chart.draw = function() {
      origDraw.apply(this, arguments);
      var ctx = chart.ctx;
      var xa = chart.scales.x;
      var ya = chart.scales.y;
      if (!xa || !ya) return;

      var xBefore = xa.getPixelForValue(labels[slotBeforeIdx]);
      var xAfter = xa.getPixelForValue(labels[slotAfterIdx]);

      var xDep;
      if (slotBeforeIdx === slotAfterIdx || jamH[slotAfterIdx] === jamH[slotBeforeIdx]) {
        xDep = xBefore;
      } else {
        var ratio = (depHourFloat - jamH[slotBeforeIdx]) / (jamH[slotAfterIdx] - jamH[slotBeforeIdx]);
        xDep = xBefore + ratio * (xAfter - xBefore);
      }

      var yTravel = ya.getPixelForValue(travelTime);
      var chartLeft = xa.left;
      var chartRight = xa.right;
      var chartTop = ya.top;
      var chartBottom = ya.bottom;

      ctx.save();
      ctx.beginPath();
      ctx.rect(chartLeft, chartTop, chartRight - chartLeft, chartBottom - chartTop);
      ctx.clip();

      // Threshold lines
      var thresholds = [
        { value: p25, label: 'P25 (Lancar)', color: '#15803d' },
        { value: mean, label: 'Mean (Sedang)', color: '#854d0e' },
        { value: p75, label: 'P75 (Padat)', color: '#c2410c' }
      ];

      thresholds.forEach(function(t) {
        var yT = ya.getPixelForValue(t.value);
        ctx.beginPath();
        ctx.moveTo(chartLeft, yT);
        ctx.lineTo(chartRight, yT);
        ctx.lineWidth = 1.2;
        ctx.strokeStyle = t.color;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // Garis vertikal merah
      ctx.beginPath();
      ctx.moveTo(xDep, chartTop);
      ctx.lineTo(xDep, chartBottom);
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#dc2626';
      ctx.setLineDash([6, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Garis horizontal dari titik ke kanan
      ctx.beginPath();
      ctx.moveTo(xDep, yTravel);
      ctx.lineTo(chartRight, yTravel);
      ctx.lineWidth = 2;
      ctx.strokeStyle = congColor;
      ctx.setLineDash([4, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Titik bulat prediksi
      ctx.beginPath();
      ctx.arc(xDep, yTravel, 8, 0, 2 * Math.PI);
      ctx.fillStyle = congColor;
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 3;
      ctx.stroke();

      // Label "Berangkat"
      ctx.fillStyle = '#dc2626';
      ctx.font = 'bold 11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Berangkat ' + seg.departure, xDep, chartTop - 8);

      ctx.restore();
      ctx.save();

      // Label di luar chart (kanan)
      var labelX = chartRight + 15;

      thresholds.forEach(function(t) {
        var yT = ya.getPixelForValue(t.value);
        if (yT < chartTop) yT = chartTop + 10;
        if (yT > chartBottom) yT = chartBottom - 5;
        ctx.fillStyle = t.color;
        ctx.font = '9px Inter, system-ui, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(t.label + ': ' + t.value.toFixed(2) + ' mnt', labelX, yT + 4);
      });

      var iconStatus;
      if (congStatus === 'Lancar') iconStatus = '🟢';
      else if (congStatus === 'Sedang') iconStatus = '🟡';
      else if (congStatus === 'Padat') iconStatus = '🟠';
      else iconStatus = '🔴';

      ctx.fillStyle = congColor;
      ctx.font = 'bold 12px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(iconStatus + ' ' + congStatus, labelX, yTravel + 4);

      ctx.fillStyle = congColor;
      ctx.font = '10px Inter, system-ui, sans-serif';
      ctx.fillText(travelTime.toFixed(1) + ' mnt', labelX, yTravel + 20);

      ctx.restore();
    };
    chart.update();

    // ── Tambahkan Threshold Info di bawah chart ──
    var chartContainer = canvas.parentElement;
    var oldInfo = chartContainer.querySelector('.threshold-info');
    if (oldInfo) oldInfo.remove();

    var thresholdInfo = document.createElement('div');
    thresholdInfo.className = 'threshold-info';
    thresholdInfo.style.cssText = 'margin-top:8px;';

    var toggleBtn = document.createElement('button');
    toggleBtn.textContent = '📊 Lihat Threshold';
    toggleBtn.style.cssText = 'padding:6px 12px; border:1px solid #e2e8f0; background:white; border-radius:6px; cursor:pointer; font-size:0.75rem; font-weight:500; font-family:Inter, system-ui, sans-serif;';

    var detailDiv = document.createElement('div');
    detailDiv.style.cssText = 'display:none; margin-top:8px; padding:10px 14px; background:#f8fafc; border-radius:8px; font-size:0.75rem; gap:16px; flex-wrap:wrap; border:1px solid #e2e8f0;';
    detailDiv.innerHTML =
      '<span style="color:#15803d; font-weight:600;">🟢 Lancar: ≤ ' + p25.toFixed(2) + ' mnt</span>' +
      '<span style="color:#854d0e; font-weight:600;">🟡 Sedang: ' + p25.toFixed(2) + ' - ' + mean.toFixed(2) + ' mnt</span>' +
      '<span style="color:#c2410c; font-weight:600;">🟠 Padat: ' + mean.toFixed(2) + ' - ' + p75.toFixed(2) + ' mnt</span>' +
      '<span style="color:#b91c1c; font-weight:600;">🔴 Macet: > ' + p75.toFixed(2) + ' mnt</span>';

    toggleBtn.onclick = function() {
      if (detailDiv.style.display === 'none' || detailDiv.style.display === '') {
        detailDiv.style.display = 'flex';
        toggleBtn.textContent = '📊 Sembunyikan Threshold';
      } else {
        detailDiv.style.display = 'none';
        toggleBtn.textContent = '📊 Lihat Threshold';
      }
    };

    thresholdInfo.appendChild(toggleBtn);
    thresholdInfo.appendChild(detailDiv);
    chartContainer.appendChild(thresholdInfo);

  } catch (e) {
    console.error('Chart error for ' + canvasId + ':', e);
  }
}

// ── Model Comparison ────────────────────────
async function loadModelComparison() {
  try {
    var data = window.DASHBOARD_DATA;
    if (!data || !data.modelMetrics) {
      document.getElementById('compBadge').textContent = 'Data model tidak tersedia';
      return;
    }

    var activeVehicle = data.activeVehicle || 'mobil';
    var otherVehicle = activeVehicle === 'mobil' ? 'motor' : 'mobil';
    var activeMetrics = data.modelMetrics;

    var res = await fetch('/api/model/metrics?vehicle=' + otherVehicle);
    if (!res.ok) throw new Error('Failed to fetch');

    var otherRaw = await res.json();
    
    var mobil, motor;
    if (activeVehicle === 'mobil') {
      mobil = activeMetrics;
      motor = {
        mae: parseFloat(otherRaw.test.mae.toFixed(4)),
        mse: parseFloat(otherRaw.test.mse.toFixed(4)),
        rmse: parseFloat(otherRaw.test.rmse.toFixed(4)),
        r2: parseFloat(otherRaw.test.r2.toFixed(4)),
        cv_mae: parseFloat(otherRaw.cv.mae_mean.toFixed(4)),
        cv_std: parseFloat(otherRaw.cv.mae_std.toFixed(4))
      };
    } else {
      motor = activeMetrics;
      mobil = {
        mae: parseFloat(otherRaw.test.mae.toFixed(4)),
        mse: parseFloat(otherRaw.test.mse.toFixed(4)),
        rmse: parseFloat(otherRaw.test.rmse.toFixed(4)),
        r2: parseFloat(otherRaw.test.r2.toFixed(4)),
        cv_mae: parseFloat(otherRaw.cv.mae_mean.toFixed(4)),
        cv_std: parseFloat(otherRaw.cv.mae_std.toFixed(4))
      };
    }

    document.getElementById('compBadge').textContent =
      'Mobil MAE: ' + mobil.mae + ' mnt | Motor MAE: ' + motor.mae + ' mnt';

    var rows = [
      { label: 'MAE (menit)', key: 'mae', lower: true },
      { label: 'MSE', key: 'mse', lower: true },
      { label: 'RMSE (menit)', key: 'rmse', lower: true },
      { label: 'R² Score', key: 'r2', lower: false },
      { label: 'CV MAE (menit)', key: 'cv_mae', lower: true },
      { label: 'CV Std', key: 'cv_std', lower: true }
    ];

    var tbody = document.getElementById('compTableBody');
    if (!tbody) return;

    tbody.innerHTML = rows.map(function(row) {
      var vm = mobil[row.key];
      var vt = motor[row.key];
      var mobilBetter = row.lower ? vm <= vt : vm >= vt;
      var motorBetter = row.lower ? vt <= vm : vt >= vm;
      var tie = vm === vt;

      var mobilStyle = mobilBetter && !tie ? 'color:#059669; font-weight:600;' : '';
      var motorStyle = motorBetter && !tie ? 'color:#059669; font-weight:600;' : '';
      var winner = tie ? 'Sama' : mobilBetter ? 'Mobil' : 'Motor';

      return '<tr>' +
        '<td style="font-weight:600;">' + row.label + '</td>' +
        '<td style="' + mobilStyle + '">' + vm + '</td>' +
        '<td style="' + motorStyle + '">' + vt + '</td>' +
        '<td>' + winner + '</td>' +
        '</tr>';
    }).join('');

  } catch (e) {
    console.error('Model comparison error:', e);
    var tbody = document.getElementById('compTableBody');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted" style="padding:20px;">Gagal memuat perbandingan</td></tr>';
    }
  }
}