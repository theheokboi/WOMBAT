async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed request: ${path}`);
  return response.json();
}

function clearLayer(layer) {
  if (layer) layer.clearLayers();
}

async function init() {
  const [ui, facilities, countryCells, adaptiveCells] = await Promise.all([
    loadJson('/v1/ui/config'),
    loadJson('/v1/facilities?limit=50000'),
    loadJson('/v1/layers/country_mask/cells'),
    loadJson('/v1/layers/facility_density_adaptive/cells?limit=100000'),
  ]);

  const [lon, lat] = ui.center;
  document.getElementById('facility-count').textContent = `Facilities loaded: ${facilities.features.length.toLocaleString()}`;
  document.getElementById('location-count').textContent = `Unique locations: ${new Set((facilities.features || []).map((f) => f.geometry.coordinates.join(','))).size.toLocaleString()}`;

  const map = L.map('map', {
    center: [lat, lon],
    zoom: ui.zoom,
    preferCanvas: true,
    zoomControl: true,
  });

  // Optional base map. If unreachable, data overlays still render.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);

  const facilityLayer = L.geoJSON(null, {
    pointToLayer: (feature, latlng) => {
      const p = feature.properties || {};
      const radius = p.facility_count
        ? Math.min(12, 2 + Math.log10(Math.max(1, Number(p.facility_count))) * 3)
        : 3;
      return L.circleMarker(latlng, {
        radius,
        color: '#ffffff',
        weight: 1,
        fillColor: '#f97316',
        fillOpacity: 0.95,
      });
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindTooltip(
        `Org: ${p.org_name || ''}<br/>` +
        `Source: ${p.source_name || ''}<br/>` +
        `H3: ${p['h3_r7'] || ''}`
      );
    },
  }).addTo(map);

  function renderFacilities() {
    clearLayer(facilityLayer);
    if (!document.getElementById('toggle-facilities').checked) return;
    facilityLayer.addData(facilities);
  }

  renderFacilities();

  const countryLayer = L.geoJSON(countryCells, {
    style: (feature) => {
      const p = feature.properties || {};
      const color = p.country_color_hex || '#1d4ed8';
      return {
        color,
        weight: 1,
        fillColor: color,
        fillOpacity: 0.18,
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindTooltip(
        `Layer: country_mask<br/>Country: ${p.layer_value || ''}<br/>Color: ${p.country_color ?? ''}<br/>H3: ${p.h3 || ''}`
      );
    },
  }).addTo(map);

  const adaptiveLayer = L.geoJSON(adaptiveCells, {
    style: (feature) => {
      const count = Number(feature?.properties?.layer_value || 0);
      const fillOpacity = Math.min(0.45, 0.1 + Math.log10(Math.max(1, count)) * 0.08);
      return {
        color: '#7c2d12',
        weight: 1,
        fillColor: '#7c2d12',
        fillOpacity,
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindTooltip(
        `Layer: facility_density_adaptive<br/>Count: ${Number(p.layer_value || 0).toLocaleString()}<br/>Resolution: r${p.resolution || ''}<br/>H3: ${p.h3 || ''}`
      );
    },
  }).addTo(map);

  const adaptiveToggle = document.getElementById('toggle-adaptive');
  function renderAdaptiveCells() {
    clearLayer(adaptiveLayer);
    if (!adaptiveToggle.checked) return;
    adaptiveLayer.addData(adaptiveCells);
  }
  renderAdaptiveCells();

  const combined = L.featureGroup([facilityLayer, countryLayer, adaptiveLayer]);
  if (combined.getBounds().isValid()) {
    map.fitBounds(combined.getBounds(), { padding: [20, 20] });
  }

  document.getElementById('toggle-facilities').addEventListener('change', (e) => {
    if (e.target.checked) {
      renderFacilities();
      return;
    }
    clearLayer(facilityLayer);
  });
  document.getElementById('toggle-country').addEventListener('change', (e) => {
    clearLayer(countryLayer);
    if (e.target.checked) countryLayer.addData(countryCells);
  });

  adaptiveToggle.addEventListener('change', () => {
    renderAdaptiveCells();
  });
}

init().catch((error) => {
  const node = document.getElementById('drilldown-content');
  node.textContent = `UI load error: ${error.message}`;
});
