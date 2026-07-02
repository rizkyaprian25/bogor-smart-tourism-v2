/**
 * Index Page — Perencanaan Itinerary
 * Update: Klik marker → muncul foto destinasi
 */

// ── State ────────────────────────────────────
let selectedDestinations = new Set();
let markers = [];
let map;
let originMarker = null;
let gmapsActive = false;
let originLat = null;
let originLon = null;
let selectedVehicle = 'mobil';

const NAMA_HARI = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
const MAX = window.APP_CONFIG?.MAX_DESTINATIONS || 5;

// ── Mapping keyword → file foto ─────────────
// Pakai keyword pendek supaya cocok meski nama
// di database panjang / ada tambahan kata
const DESTINATION_PHOTOS = [
  { keywords: ['kebun raya'],                    url: '/static/images/Kebun_Raya_Bogor.jpg'          },
  { keywords: ['taman heulang'],                 url: '/static/images/Taman_Heulang.jpg'              },
  { keywords: ['rivera'],                        url: '/static/images/Rivera_Outbound.jpg'            },
  { keywords: ['tirtania'],                      url: '/static/images/Tirtania_Waterpark.jpg'         },
  { keywords: ['aquagame', 'wibit'],             url: '/static/images/Bogor_Aquagame.jpg'             },
  { keywords: ['kuntum'],                        url: '/static/images/Kuntum_Farmfield.jpg'           },
  { keywords: ['museum peta', 'peta'],           url: '/static/images/Museum_PETA.jpg'                },
  { keywords: ['fullbelly'],                     url: '/static/images/Fullbelly_sport.jpg'            },
  { keywords: ['kampung durian', 'rancamaya'],   url: '/static/images/Kampung_Durian_rancamaya.jpg'  },
  { keywords: ['bts', 'bamboo'],                 url: '/static/images/BTS.jpg'                        },
];

/**
 * Cari foto berdasarkan nama — keyword matching
 * Cocok meski nama di DB lebih panjang dari yang diharapkan
 */
function getPhotoUrl(name) {
  if (!name) return null;
  const lower = name.toLowerCase();
  for (const entry of DESTINATION_PHOTOS) {
    if (entry.keywords.some(kw => lower.includes(kw))) {
      return entry.url;
    }
  }
  return null;
}

/**
 * Buat konten popup dengan foto untuk halaman index
 * (popup lebih ringkas, hanya nama & kategori + foto)
 */
function buildIndexPopup({ id, name, category, jamOperasional }) {
  const photoUrl = getPhotoUrl(name);

  const photoHtml = photoUrl
    ? `<div style="
        width:100%;
        height:130px;
        overflow:hidden;
        border-radius:8px;
        margin-bottom:8px;
        background:#f1f5f9;
      ">
        <img
          src="${photoUrl}"
          alt="${name}"
          style="
            width:100%;
            height:100%;
            object-fit:cover;
            display:block;
          "
          onerror="this.parentElement.style.display='none'"
        />
      </div>`
    : '';

  const operasionalHtml = jamOperasional && jamOperasional !== '-'
    ? `<div style="
        margin-top:6px;
        font-size:0.68rem;
        color:#64748b;
        background:#f1f5f9;
        border-radius:4px;
        padding:4px 8px;
      ">🕒 Operasional: ${jamOperasional}</div>`
    : '';

  return `
    <div style="
      font-family:'Inter',system-ui,sans-serif;
      min-width:190px;
      max-width:220px;
    ">
      ${photoHtml}
      <div style="
        font-size:0.65rem;
        font-weight:600;
        color:#94a3b8;
        text-transform:uppercase;
        letter-spacing:0.04em;
        margin-bottom:3px;
      ">Destinasi #${id}</div>
      <div style="
        font-size:0.88rem;
        font-weight:700;
        color:#111827;
        margin-bottom:2px;
        line-height:1.3;
      ">${name}</div>
      <div style="
        font-size:0.72rem;
        color:#6b7280;
      ">${category || ''}</div>
      ${operasionalHtml}
    </div>`;
}

// ── Init ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  initMap();
  loadAllMarkers();
  setupEventListeners();
  startRealtimeClock();
});

// ── Real-Time Clock ──────────────────────────
function startRealtimeClock() {
  async function updateTime() {
    try {
      const response = await fetch('/api/debug/time');
      const data = await response.json();

      const clockEl = document.getElementById('realtimeClock');
      const dayEl   = document.getElementById('realtimeDay');

      if (clockEl && data.wib_time) {
        const timePart = data.wib_time.split(' ')[1] || '--:--';
        clockEl.textContent = timePart.substring(0, 5);
      }

      if (dayEl) {
        const now     = new Date();
        const tanggal = now.toLocaleDateString('id-ID', {
          day: 'numeric', month: 'long', year: 'numeric'
        });
        dayEl.textContent = `${data.wib_hari}, ${tanggal}`;
      }
    } catch (error) {
      console.warn('Clock fallback to local:', error);
      const now     = new Date();
      const jam     = now.getHours().toString().padStart(2, '0');
      const mnt     = now.getMinutes().toString().padStart(2, '0');
      const hari    = NAMA_HARI[now.getDay()];
      const tanggal = now.toLocaleDateString('id-ID', {
        day: 'numeric', month: 'long', year: 'numeric'
      });

      const clockEl = document.getElementById('realtimeClock');
      const dayEl   = document.getElementById('realtimeDay');
      if (clockEl) clockEl.textContent = `${jam}:${mnt}`;
      if (dayEl)   dayEl.textContent   = `${hari}, ${tanggal}`;
    }
  }

  updateTime();
  setInterval(updateTime, 1000);
}

// ── Map ──────────────────────────────────────
function initMap() {
  map = L.map('map').setView([-6.62, 106.82], 12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
  }).addTo(map);
}

async function loadAllMarkers() {
  try {
    const locs = await fetch('/api/locations').then(r => r.json());

    locs.forEach(loc => {
      if (loc.ID === 0) return;

      // Icon abu-abu (belum dipilih)
      const icon = L.divIcon({
        className: '',
        html: `<div style="
          background:#94a3b8;
          color:white;
          width:28px;height:28px;
          border-radius:50%;
          display:flex;align-items:center;justify-content:center;
          font-weight:600;font-size:0.7rem;
          border:2px solid white;
          box-shadow:0 1px 4px rgba(0,0,0,0.15);
          cursor:pointer;
        ">${loc.ID}</div>`,
        iconSize  : [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -16]
      });

      // Popup dengan foto
      const popupContent = buildIndexPopup({
        id      : loc.ID,
        name    : loc.Nama_Tempat,
        category: loc.Kategori,
        jamOperasional: loc.jam_operasional,
      });

      const m = L.marker([loc.Latitude, loc.Longitude], { icon })
        .bindPopup(popupContent, {
          maxWidth   : 240,
          className  : 'dest-popup',
          closeButton: true,
        })
        .addTo(map);

      m._id       = loc.ID;
      m._name     = loc.Nama_Tempat;
      m._category = loc.Kategori;
      m._jamOperasional = loc.jam_operasional;
      markers.push(m);
    });
  } catch (e) {
    console.error('Failed to load locations:', e);
  }
}

// ── Event Listeners ──────────────────────────
function setupEventListeners() {
  // Search filter
  document.getElementById('searchInput').addEventListener('input', function (e) {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('.dest-item').forEach(item => {
      const show =
        item.dataset.name.toLowerCase().includes(q) ||
        item.dataset.category.toLowerCase().includes(q);
      item.style.display = show ? '' : 'none';
    });
  });

  // Checkbox change
  document.querySelectorAll('.dest-check').forEach(cb => {
    cb.addEventListener('change', function () {
      const item = this.closest('.dest-item');
      const id   = parseInt(this.value);

      if (this.checked) {
        if (selectedDestinations.size >= MAX) {
          alert('Maksimal ' + MAX + ' destinasi!');
          this.checked = false;
          return;
        }
        selectedDestinations.add(id);
        item.classList.add('selected');
        highlightMarker(id, true);
      } else {
        selectedDestinations.delete(id);
        item.classList.remove('selected');
        highlightMarker(id, false);
      }

      updateSelectedCount();
      updateMapMarkers();
    });
  });
}

// ── Vehicle ──────────────────────────────────
function setVehicleType(type) {
  selectedVehicle = type;
  console.log('Vehicle:', type);
}

// ── TomTom Toggle ────────────────────────────
function toggleTomTom() {
  gmapsActive = !gmapsActive;
  const toggle = document.getElementById('tomtomToggle');
  const body   = document.getElementById('tomtomBody');
  const off    = document.getElementById('tomtomOffInfo');
  const legend = document.getElementById('legendOrigin');

  if (gmapsActive) {
    toggle.classList.add('on');
    body.classList.add('show');
    if (off)    off.style.display    = 'none';
    if (legend) legend.style.display = 'flex';
  } else {
    toggle.classList.remove('on');
    body.classList.remove('show');
    if (off)    off.style.display    = 'block';
    if (legend) legend.style.display = 'none';
    if (originMarker) {
      map.removeLayer(originMarker);
      originMarker = null;
    }
    originLat = null;
    originLon = null;
  }
}

function detectLocation() {
  if (!navigator.geolocation) {
    showToast('GPS tidak tersedia.');
    return;
  }

  const btn     = document.getElementById('locateBtn');
  btn.textContent = 'Mendeteksi...';
  btn.disabled    = true;

  navigator.geolocation.getCurrentPosition(
    pos => {
      originLat = pos.coords.latitude;
      originLon = pos.coords.longitude;
      onOriginSet();
      btn.textContent = 'Terdeteksi — Deteksi Ulang';
      btn.disabled    = false;
    },
    err => {
      showToast('Gagal: ' + err.message);
      btn.textContent = 'Deteksi Lokasi Saya';
      btn.disabled    = false;
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

function onCoordsManual() {
  const lat = parseFloat(document.getElementById('originLat').value);
  const lon = parseFloat(document.getElementById('originLon').value);
  if (!isNaN(lat) && !isNaN(lon) && lat >= -8 && lat <= -5 && lon >= 105 && lon <= 108) {
    originLat = lat;
    originLon = lon;
    onOriginSet();
  }
}

function onOriginSet() {
  document.getElementById('originLat').value = originLat.toFixed(6);
  document.getElementById('originLon').value = originLon.toFixed(6);

  const display = document.getElementById('coordsDisplay');
  document.getElementById('coordsText').textContent =
    `${originLat.toFixed(5)}, ${originLon.toFixed(5)}`;
  display.style.display = 'block';

  if (originMarker) map.removeLayer(originMarker);

  originMarker = L.marker([originLat, originLon], {
    icon: L.divIcon({
      className: '',
      html: `<div style="
        background:#059669;color:white;
        width:32px;height:32px;border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        font-size:0.8rem;border:2px solid white;
        box-shadow:0 2px 8px rgba(5,150,105,0.3);
      ">📍</div>`,
      iconSize  : [32, 32],
      iconAnchor: [16, 16]
    })
  }).bindPopup('<b>Titik Awal Anda</b>').addTo(map);

  map.setView([originLat, originLon], 13);
}

// ── Markers ──────────────────────────────────
function highlightMarker(id, on) {
  const m = markers.find(m => m._id === id);
  if (!m) return;

  if (on) {
    // Biru — dipilih
    m.setIcon(L.divIcon({
      className: '',
      html: `<div style="
        background:#2563eb;color:white;
        width:32px;height:32px;border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        font-weight:600;font-size:0.7rem;
        border:2px solid white;
        box-shadow:0 2px 8px rgba(37,99,235,0.3);
        cursor:pointer;
      ">${id}</div>`,
      iconSize   : [32, 32],
      iconAnchor : [16, 16],
      popupAnchor: [0, -18]
    }));
  } else {
    // Abu-abu — belum dipilih
    m.setIcon(L.divIcon({
      className: '',
      html: `<div style="
        background:#94a3b8;color:white;
        width:28px;height:28px;border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        font-weight:600;font-size:0.7rem;
        border:2px solid white;
        cursor:pointer;
      ">${id}</div>`,
      iconSize   : [28, 28],
      iconAnchor : [14, 14],
      popupAnchor: [0, -16]
    }));
  }

  // Perbarui popup content (foto tetap muncul)
  const popupContent = buildIndexPopup({
    id      : id,
    name    : m._name,
    category: m._category,
    jamOperasional: m._jamOperasional,
  });
  m.setPopupContent(popupContent);
}

function updateMapMarkers() {
  markers.forEach(m => map.removeLayer(m));

  const bounds = [];
  markers.forEach(m => {
    if (selectedDestinations.has(m._id)) {
      m.addTo(map);
      bounds.push(m.getLatLng());
    }
  });

  if (originMarker) bounds.push(originMarker.getLatLng());
  if (bounds.length > 0) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50] });
  }
}

// ── Service Time ─────────────────────────────
function setServiceTime(id, min) {
  const input = document.getElementById(`service-${id}`);
  if (input) input.value = min;
}

function updateSelectedCount() {
  document.getElementById('selectedCount').textContent = selectedDestinations.size;
}

// ── Plan Trip ────────────────────────────────
async function planTrip() {
  const selectedIds = Array.from(selectedDestinations);

  if (selectedIds.length < window.APP_CONFIG.MIN_DESTINATIONS) {
    showToast('Pilih minimal ' + window.APP_CONFIG.MIN_DESTINATIONS + ' destinasi!');
    return;
  }

  let oLat = null, oLon = null;
  if (gmapsActive) {
    if (!originLat || !originLon) {
      showToast('Aktifkan TomTom: deteksi atau isi koordinat!');
      return;
    }
    oLat = originLat;
    oLon = originLon;
  }

  const serviceTimes = {};
  selectedIds.forEach(id => {
    serviceTimes[id] = parseInt(document.getElementById(`service-${id}`).value) || 60;
  });

  showLoading(true, 'Menghitung rute optimal...');

  try {
    const body = {
      selected_ids : selectedIds,
      service_times: serviceTimes,
      vehicle_type : selectedVehicle,
    };
    if (gmapsActive && oLat && oLon) {
      body.origin_lat = oLat;
      body.origin_lon = oLon;
    }

    const data = await fetch('/api/plan', {
      method : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body   : JSON.stringify(body)
    }).then(r => r.json());

    if (data.error) {
      showToast(data.error);
      return;
    }
    window.location.href = data.redirect;
  } catch (e) {
    showToast('Error: ' + e.message);
  } finally {
    showLoading(false);
  }
}