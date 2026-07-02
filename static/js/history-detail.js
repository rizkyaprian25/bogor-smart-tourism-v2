/**
 * History Detail Page — Map
 * Update: Klik marker → muncul foto destinasi
 */

// ── Mapping keyword → file foto ──────
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
 * Buat konten popup dengan foto untuk halaman history detail
 * (paling lengkap: foto + nama + detail segmen + jam operasional)
 */
function buildDetailPopup({ isOrigin, spotIdx, node, seg }) {
  const photoUrl   = getPhotoUrl(node.name);
  const headerColor = isOrigin ? '#059669' : '#2563eb';
  const headerLabel = isOrigin ? 'Titik Awal' : `Destinasi #${spotIdx}`;

  const photoHtml = photoUrl
    ? `<div style="
        width:100%;
        height:140px;
        overflow:hidden;
        border-radius:8px;
        margin-bottom:10px;
        background:#f1f5f9;
      ">
        <img
          src="${photoUrl}"
          alt="${node.name}"
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

  let detailHtml = '';
  if (!isOrigin && seg) {
    const methodLabel = seg.is_tomtom ? '🛰 TomTom' : '🤖 RF';
    detailHtml = `
      <div style="
        display:flex;
        flex-direction:column;
        gap:4px;
        font-size:0.72rem;
        color:#374151;
        background:#f8fafc;
        border-radius:6px;
        padding:8px 10px;
        margin-top:6px;
      ">
        <span>${methodLabel}: <b>${seg.travel_time} menit</b></span>
        <span>📍 Jarak: <b>${seg.distance_km} km</b></span>
        <span>🕐 Tiba: <b>${seg.arrival}</b></span>
        <span>🏖 Kunjungan: <b>${seg.service_time} menit</b></span>
        <span>🚀 Lanjut: <b>${seg.depart_next}</b></span>
      </div>`;
  }

  const operasionalHtml = node.jam_operasional
    ? `<div style="
        margin-top:6px;
        font-size:0.68rem;
        color:#64748b;
        background:#f1f5f9;
        border-radius:4px;
        padding:4px 8px;
      ">🕒 Operasional: ${node.jam_operasional}</div>`
    : '';

  return `
    <div style="
      font-family:'Inter',system-ui,sans-serif;
      min-width:200px;
      max-width:250px;
    ">
      ${photoHtml}
      <div style="
        font-weight:700;
        font-size:0.72rem;
        color:${headerColor};
        text-transform:uppercase;
        letter-spacing:0.04em;
        margin-bottom:3px;
      ">${headerLabel}</div>
      <div style="
        font-size:0.88rem;
        font-weight:600;
        color:#111827;
        margin-bottom:2px;
        line-height:1.3;
      ">${node.name}</div>
      ${detailHtml}
      ${operasionalHtml}
    </div>`;
}

// ── Init ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  initDetailMap();
});

function initDetailMap() {
  const data = window.HISTORY_DETAIL;
  if (!data || !data.nodesInfo) return;

  const nodesInfo = data.nodesInfo;
  const segments  = data.segments || [];

  const map = L.map('map').setView([-6.62, 106.82], 12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
  }).addTo(map);

  const bounds  = [];
  let spotIdx   = 0;

  const colors = [
    '#2563eb', '#7c3aed', '#dc2626',
    '#d97706', '#059669', '#eab308'
  ];

  nodesInfo.forEach((node, idx) => {
    let label, bgColor;
    const isOrigin = node.is_origin;
    const size     = isOrigin ? 42 : 36;

    if (isOrigin) {
      label   = '📍';
      bgColor = '#059669';
    } else {
      spotIdx++;
      label   = spotIdx.toString();
      bgColor = colors[(spotIdx - 1) % colors.length];
    }

    const icon = L.divIcon({
      className: '',
      html: `<div style="
        background:${bgColor};
        color:white;
        width:${size}px;height:${size}px;
        border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        font-size:${isOrigin ? '0.9rem' : '0.75rem'};
        font-weight:700;
        border:2px solid white;
        box-shadow:0 2px 8px rgba(0,0,0,0.2);
        cursor:pointer;
      ">${label}</div>`,
      iconSize   : [size, size],
      iconAnchor : [size / 2, size / 2],
      popupAnchor: [0, -(size / 2) - 4]
    });

    const seg          = segments.find(s => s.to_name === node.name);
    const popupContent = buildDetailPopup({ isOrigin, spotIdx, node, seg });

    L.marker([node.lat, node.lon], { icon })
      .bindPopup(popupContent, {
        maxWidth   : 270,
        className  : 'dest-popup',
        closeButton: true,
      })
      .addTo(map);

    bounds.push([node.lat, node.lon]);
  });

  if (bounds.length > 0) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40] });
  }
}