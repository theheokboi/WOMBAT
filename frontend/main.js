async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed request: ${path}`);
  return response.json();
}

function clearLayer(layer) {
  if (layer) layer.clearLayers();
}

function aggregateFacilities(geojson) {
  const buckets = new Map();
  for (const feature of geojson.features || []) {
    const [lon, lat] = feature.geometry.coordinates;
    const key = `${lat.toFixed(6)},${lon.toFixed(6)}`;
    const current = buckets.get(key);
    if (!current) {
      buckets.set(key, {
        lat,
        lon,
        count: 1,
        sample: feature.properties || {},
      });
    } else {
      current.count += 1;
    }
  }
  const features = [];
  for (const entry of buckets.values()) {
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [entry.lon, entry.lat] },
      properties: {
        ...entry.sample,
        facility_count: entry.count,
      },
    });
  }
  return { type: 'FeatureCollection', features };
}

function beeswarmFacilities(geojson) {
  const buckets = new Map();
  for (const feature of geojson.features || []) {
    const [lon, lat] = feature.geometry.coordinates;
    const key = `${lat.toFixed(6)},${lon.toFixed(6)}`;
    const current = buckets.get(key);
    if (!current) {
      buckets.set(key, {
        lat,
        lon,
        items: [feature],
      });
    } else {
      current.items.push(feature);
    }
  }

  // Deterministic beeswarm layout using a sunflower pattern per co-located bucket.
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const stepMeters = 300;
  const features = [];
  for (const entry of buckets.values()) {
    const sorted = entry.items
      .slice()
      .sort((a, b) => String(a.properties?.facility_id || '').localeCompare(String(b.properties?.facility_id || '')));

    for (let i = 0; i < sorted.length; i += 1) {
      const feature = sorted[i];
      const radiusMeters = i === 0 ? 0 : stepMeters * Math.sqrt(i);
      const theta = i * goldenAngle;
      const dx = radiusMeters * Math.cos(theta);
      const dy = radiusMeters * Math.sin(theta);
      const dLat = dy / 111320;
      const cosLat = Math.max(0.2, Math.cos((entry.lat * Math.PI) / 180));
      const dLon = dx / (111320 * cosLat);

      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [entry.lon + dLon, entry.lat + dLat] },
        properties: {
          ...(feature.properties || {}),
          colocated_count: sorted.length,
          colocated_index: i + 1,
        },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

function uniqueSortedResolutions(zoomToH3) {
  return Array.from(new Set(Object.values(zoomToH3 || {}).map((value) => Number(value))))
    .filter((value) => Number.isInteger(value))
    .sort((a, b) => a - b);
}

function suggestedResolution(zoom, zoomToH3, fallback) {
  const entries = Object.entries(zoomToH3 || {})
    .map(([threshold, resolution]) => [Number(threshold), Number(resolution)])
    .filter(([threshold, resolution]) => Number.isFinite(threshold) && Number.isInteger(resolution))
    .sort((a, b) => a[0] - b[0]);

  let selected = fallback;
  for (const [threshold, resolution] of entries) {
    if (zoom >= threshold) selected = resolution;
  }
  return selected;
}

function normalizeLng(value) {
  let lon = Number(value);
  while (lon < -180) lon += 360;
  while (lon > 180) lon -= 360;
  return lon;
}

function viewportPolygons(bounds) {
  const south = Math.max(-85, Number(bounds.getSouth()));
  const north = Math.min(85, Number(bounds.getNorth()));
  const west = normalizeLng(bounds.getWest());
  const east = normalizeLng(bounds.getEast());

  const polygon = (minLng, maxLng) => ({
    type: 'Polygon',
    coordinates: [[
      [minLng, south],
      [maxLng, south],
      [maxLng, north],
      [minLng, north],
      [minLng, south],
    ]],
  });

  if (west <= east) {
    return [polygon(west, east)];
  }
  return [polygon(west, 180), polygon(-180, east)];
}

function polygonToCellsCompat(h3lib, polygon, resolution) {
  if (typeof h3lib.polygonToCells === 'function') {
    try {
      return h3lib.polygonToCells(polygon, resolution, true);
    } catch (error) {
      const latLng = polygon.coordinates[0].map(([lng, lat]) => [lat, lng]);
      return h3lib.polygonToCells(latLng, resolution, false);
    }
  }
  if (typeof h3lib.polyfill === 'function') {
    return h3lib.polyfill(polygon.coordinates, resolution, true);
  }
  throw new Error('h3-js polygon fill API unavailable');
}

function cellBoundaryCompat(h3lib, cell) {
  if (typeof h3lib.cellToBoundary === 'function') {
    return h3lib.cellToBoundary(cell).map(([lat, lng]) => [lng, lat]);
  }
  if (typeof h3lib.h3ToGeoBoundary === 'function') {
    return h3lib.h3ToGeoBoundary(cell, true).map(([lat, lng]) => [lng, lat]);
  }
  throw new Error('h3-js boundary API unavailable');
}

function colorForResolution(resolution) {
  const palette = ['#b91c1c', '#c2410c', '#ca8a04', '#15803d', '#0f766e', '#0369a1', '#1d4ed8', '#7c3aed'];
  return palette[Math.abs(Number(resolution)) % palette.length];
}

async function init() {
  const [ui, facilities, countryCells, adaptiveCells] = await Promise.all([
    loadJson('/v1/ui/config'),
    loadJson('/v1/facilities?limit=50000'),
    loadJson('/v1/layers/country_mask/cells'),
    loadJson('/v1/layers/facility_density_adaptive/cells?limit=100000'),
  ]);

  const [lon, lat] = ui.center;
  const beeswarm = beeswarmFacilities(facilities);
  const aggregated = aggregateFacilities(facilities);
  const raw = facilities;
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
      if (p.facility_count) {
        layer.bindTooltip(
          `Facilities: ${Number(p.facility_count || 1).toLocaleString()}<br/>` +
          `Org sample: ${p.org_name || ''}<br/>` +
          `Source sample: ${p.source_name || ''}<br/>` +
          `H3: ${p['h3_r7'] || ''}`
        );
        return;
      }
      layer.bindTooltip(
        `Org: ${p.org_name || ''}<br/>` +
        `Source: ${p.source_name || ''}<br/>` +
        `Co-located group: ${Number(p.colocated_count || 1).toLocaleString()}<br/>` +
        `Group index: ${Number(p.colocated_index || 1).toLocaleString()}<br/>` +
        `H3: ${p['h3_r7'] || ''}`
      );
    },
  }).addTo(map);

  function currentFacilityData() {
    const mode = document.getElementById('facility-style').value;
    if (mode === 'raw') return raw;
    if (mode === 'aggregated') return aggregated;
    return beeswarm;
  }

  function renderFacilities() {
    clearLayer(facilityLayer);
    if (!document.getElementById('toggle-facilities').checked) return;
    facilityLayer.addData(currentFacilityData());
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
  document.getElementById('facility-style').addEventListener('change', () => {
    renderFacilities();
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
