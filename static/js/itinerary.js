/**
 * Itinerary Page — Map & Timeline
 * Update: Klik marker → muncul foto destinasi
 */

// ── Mapping keyword → file foto ─────────────────────────────
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
 * Buat konten popup dengan foto
 */
function buildPopupContent({ isOrigin, spotIndex, name, seg, jamOperasional }) {
  const photoUrl = getPhotoUrl(name);

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

  const headerColor = isOrigin ? '#059669' : '#2563eb';
  const headerLabel = isOrigin ? 'Titik Awal' : `Destinasi #${spotIndex}`;

  let detailHtml = '';
  if (!isOrigin && seg) {
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
        <span>⏱ Waktu tempuh: <b>${seg.travel_time} menit</b></span>
        <span>📍 Jarak: <b>${seg.distance_km} km</b></span>
        <span>🕐 Tiba: <b>${seg.arrival}</b></span>
        <span>🏖 Kunjungan: <b>${seg.service_time} menit</b></span>
      </div>`;
  }

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
      font-family: 'Inter', system-ui, sans-serif;
      min-width: 200px;
      max-width: 240px;
    ">
      ${photoHtml}
      <div style="
        font-weight: 700;
        font-size: 0.72rem;
        color: ${headerColor};
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 3px;
      ">${headerLabel}</div>
      <div style="
        font-size: 0.88rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 2px;
        line-height: 1.3;
      ">${name}</div>
      ${detailHtml}
      ${operasionalHtml}
    </div>`;
}

// ── Init Map ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  initItineraryMap();
});

function initItineraryMap() {
  const data = window.ITINERARY_DATA;
  if (!data) return;

  const nodesInfo = data.nodesInfo;
  const itinerary = data.itinerary;

  const map = L.map('map').setView([-6.62, 106.82], 12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
  }).addTo(map);

  const bounds   = [];
  let spotIndex  = 0;

  const routeColors = [
    '#2563eb', '#7c3aed', '#059669',
    '#d97706', '#dc2626', '#eab308',
    '#ec4899', '#0d9488'
  ];

  nodesInfo.forEach((node, idx) => {
    let label, bgColor;
    const size = node.is_origin ? 40 : 36;

    if (node.is_origin) {
      label   = '📍';
      bgColor = '#059669';
    } else {
      spotIndex++;
      label   = spotIndex.toString();
      bgColor = routeColors[(spotIndex - 1) % routeColors.length];
    }

    const icon = L.divIcon({
      className: '',
      html: `<div style="
        background:${bgColor};
        color:white;
        width:${size}px;
        height:${size}px;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        font-size:${node.is_origin ? '0.9rem' : '0.75rem'};
        font-weight:700;
        border:2px solid white;
        box-shadow:0 2px 8px rgba(0,0,0,0.25);
        cursor:pointer;
        transition:transform 0.15s;
      ">${label}</div>`,
      iconSize     : [size, size],
      iconAnchor   : [size / 2, size / 2],
      popupAnchor  : [0, -(size / 2) - 4]
    });

    const seg            = itinerary.find(s => s.to_name === node.name);
    const popupContent   = buildPopupContent({
      isOrigin   : node.is_origin,
      spotIndex,
      name       : node.name,
      seg,
      jamOperasional: node.jam_operasional
    });

    const marker = L.marker([node.lat, node.lon], { icon })
      .bindPopup(popupContent, {
        maxWidth    : 260,
        className   : 'dest-popup',
        closeButton : true,
      })
      .addTo(map);

    // Auto-buka popup marker pertama (wisata pertama, bukan origin)
    if (idx === 1 || (nodesInfo.length === 1 && idx === 0)) {
      setTimeout(() => marker.openPopup(), 600);
    }

    bounds.push([node.lat, node.lon]);
  });

  if (bounds.length > 0) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50] });
  }
}