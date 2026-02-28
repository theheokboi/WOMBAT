async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed request: ${path}`);
  return response.json();
}

async function tryLoadJson(path) {
  try {
    return await loadJson(path);
  } catch (_error) {
    return null;
  }
}

const GB_COUNTRY_CODE = 'GB';

function clearLayer(layer) {
  if (layer) layer.clearLayers();
}

function toNumeric(value) {
  if (value === null || value === undefined || value === '') return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getAdaptiveLeafCount(properties) {
  if (properties && properties.leaf_facility_count !== undefined) {
    return toNumeric(properties.leaf_facility_count);
  }
  if (properties && properties.layer_value !== undefined) {
    return toNumeric(properties.layer_value);
  }
  if (properties && properties.facility_count !== undefined) {
    return toNumeric(properties.facility_count);
  }
  return 0;
}

function getAdaptiveResolution(properties) {
  if (!properties) return '';
  if (properties.resolution !== undefined && properties.resolution !== null) return properties.resolution;
  if (properties.leaf_resolution !== undefined && properties.leaf_resolution !== null) return properties.leaf_resolution;
  return '';
}

function getAdaptiveH3(properties) {
  if (!properties) return '';
  if (properties.h3) return properties.h3;
  if (properties.h3_index) return properties.h3_index;
  if (properties.cell) return properties.cell;
  return '';
}

function featureCollectionFeatures(collection) {
  return Array.isArray(collection && collection.features) ? collection.features : [];
}

function normalizeCountryCode(value) {
  if (value === null || value === undefined) return '';
  const normalized = String(value).trim().toUpperCase();
  if (normalized.length === 2) return normalized;
  return '';
}

function getFeatureH3Candidates(properties) {
  if (!properties) return [];
  const out = [];
  for (const key of ['h3', 'h3_index', 'cell']) {
    if (properties[key]) out.push(String(properties[key]));
  }
  for (const [key, value] of Object.entries(properties)) {
    if (/^h3_r\d+$/.test(key) && value) out.push(String(value));
  }
  return out;
}

function isGbCountryFeature(feature) {
  const code = normalizeCountryCode(feature?.properties?.layer_value);
  return code === GB_COUNTRY_CODE;
}

function buildCountryCellSet(features) {
  const cells = new Set();
  for (const feature of features || []) {
    const cell = feature?.properties?.h3;
    if (cell) cells.add(String(cell));
  }
  return cells;
}

function cellInCountryMask(cell, countryCellSet) {
  if (!cell || !countryCellSet || countryCellSet.size === 0 || !window.h3) return false;
  const value = String(cell);
  if (countryCellSet.has(value)) return true;
  try {
    const resolution = h3.getResolution(value);
    for (let res = resolution - 1; res >= 0; res -= 1) {
      const parent = h3.cellToParent(value, res);
      if (countryCellSet.has(parent)) return true;
    }
  } catch (_error) {
    return false;
  }
  return false;
}

function featureIsGbScoped(feature, countryCellSet) {
  const properties = feature?.properties || {};
  const countryCodeCandidates = [
    properties.layer_value,
    properties.country_code,
    properties.country,
    properties.country_iso,
    properties.country_iso2,
  ].map(normalizeCountryCode).filter(Boolean);

  if (countryCodeCandidates.length > 0) {
    return countryCodeCandidates.some((code) => code === GB_COUNTRY_CODE);
  }

  const cells = getFeatureH3Candidates(properties);
  return cells.some((cell) => cellInCountryMask(cell, countryCellSet));
}

async function init() {
  const [ui, facilities, countryCells, adaptiveCells, adaptiveMetadata, latestStatus, activeStatus, calibrationLatest] = await Promise.all([
    loadJson('/v1/ui/config'),
    loadJson('/v1/facilities?limit=50000'),
    loadJson('/v1/layers/country_mask/cells'),
    loadJson('/v1/layers/facility_density_adaptive/cells?limit=100000'),
    tryLoadJson('/v1/layers/facility_density_adaptive/metadata'),
    tryLoadJson('/v1/runs/latest/status'),
    tryLoadJson('/v1/runs/active/status'),
    tryLoadJson('/v1/calibration/latest'),
  ]);
  const countryFeatures = featureCollectionFeatures(countryCells);
  const gbCountryFeatures = countryFeatures.filter((feature) => isGbCountryFeature(feature));
  const gbCountryCellSet = buildCountryCellSet(gbCountryFeatures);

  const facilitiesFeatures = featureCollectionFeatures(facilities);
  const gbFacilitiesFeatures = facilitiesFeatures.filter((feature) => featureIsGbScoped(feature, gbCountryCellSet));
  const gbFacilities = { ...facilities, features: gbFacilitiesFeatures };

  const adaptiveFeatures = featureCollectionFeatures(adaptiveCells);
  const gbAdaptiveFeatures = adaptiveFeatures.filter((feature) => featureIsGbScoped(feature, gbCountryCellSet));
  const gbCountryCells = { ...countryCells, features: gbCountryFeatures };

  const adaptivePolicyName = adaptiveMetadata?.policy_name || adaptiveMetadata?.policy?.name || null;
  const policyVersion = adaptiveMetadata?.layer_version || latestStatus?.adaptive_policy?.layer_version || '--';

  const [lon, lat] = ui.center;
  document.getElementById('facility-count').textContent = `GB facilities loaded: ${gbFacilities.features.length.toLocaleString()}`;
  document.getElementById('location-count').textContent = `GB unique locations: ${new Set((gbFacilities.features || []).map((f) => f.geometry.coordinates.join(','))).size.toLocaleString()}`;
  const displayScopeNode = document.getElementById('display-scope');
  const latestAdaptiveVersionNode = document.getElementById('latest-adaptive-version');
  const adaptivePolicyNode = document.getElementById('adaptive-policy');
  const runtimeExpectationNode = document.getElementById('runtime-expectation');
  const latestRunRuntimeNode = document.getElementById('latest-run-runtime');
  const activeRunStatusNode = document.getElementById('active-run-status');
  const calibrationBasisNode = document.getElementById('calibration-basis');
  displayScopeNode.textContent = `Display scope: GB only (country_mask=GB, filtered in UI; ${gbCountryFeatures.length.toLocaleString()} country cells, ${gbAdaptiveFeatures.length.toLocaleString()} adaptive cells)`;

  const latestRunId = latestStatus?.run_id || '--';
  const latestPolicyName = latestStatus?.adaptive_policy?.policy_name || adaptivePolicyName || '--';
  const latestPolicyVersion = latestStatus?.adaptive_policy?.layer_version || policyVersion || '--';
  latestAdaptiveVersionNode.textContent =
    `Latest published adaptive version: ${latestRunId} | ${latestPolicyName} | ${latestPolicyVersion}`;

  adaptivePolicyNode.textContent = `Adaptive policy: ${adaptivePolicyName || '--'} (${policyVersion})`;

  const makeRunTypical = latestStatus?.runtime_expectations?.make_run?.typical_minutes || '--';
  const makeRunSlow = latestStatus?.runtime_expectations?.make_run?.slow_path_minutes || '--';
  runtimeExpectationNode.textContent = `Runtime expectation: make run typical ${makeRunTypical} min, slow path ${makeRunSlow} min`;

  const latestRuntimeSeconds = latestStatus?.metrics?.run_duration_seconds;
  if (typeof latestRuntimeSeconds === 'number') {
    latestRunRuntimeNode.textContent = `Latest run runtime: ${(latestRuntimeSeconds / 60).toFixed(2)} min`;
  } else {
    latestRunRuntimeNode.textContent = 'Latest run runtime: --';
  }

  if (activeStatus?.active) {
    const stage = activeStatus?.active_status?.stage || '--';
    const elapsed = activeStatus?.active_status?.elapsed_s;
    const elapsedLabel = typeof elapsed === 'number' ? `${elapsed.toFixed(1)}s` : '--';
    activeRunStatusNode.textContent = `Active run: in progress (${stage}, elapsed ${elapsedLabel})`;
  } else {
    activeRunStatusNode.textContent = 'Active run: none';
  }

  if (calibrationLatest) {
    const calibrationId = calibrationLatest.calibration_id || '--';
    const basisCountry = calibrationLatest.country || calibrationLatest.country_code || calibrationLatest.scope?.country || '--';
    const basisRuntime =
      calibrationLatest.runtime_seconds
      ?? calibrationLatest.run_duration_seconds
      ?? calibrationLatest.metrics?.run_duration_seconds;
    const runtimeLabel = typeof basisRuntime === 'number' ? `${basisRuntime.toFixed(2)}s` : '--';
    calibrationBasisNode.textContent = `Calibration basis: ${basisCountry} (${calibrationId}), runtime ${runtimeLabel}`;
  } else {
    calibrationBasisNode.textContent = 'Calibration basis: unavailable';
  }

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
    facilityLayer.addData(gbFacilities);
  }

  renderFacilities();

  const countryLayer = L.geoJSON(gbCountryCells, {
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

  const adaptiveLayer = L.geoJSON(null, {
    style: (feature) => {
      const count = getAdaptiveLeafCount(feature?.properties || {});
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
      const tooltipLines = [
        'Layer: facility_density_adaptive',
        `Leaf facility count: ${getAdaptiveLeafCount(p).toLocaleString()}`,
        `Resolution: r${getAdaptiveResolution(p)}`,
        `H3: ${getAdaptiveH3(p)}`,
      ];
      if (adaptivePolicyName) {
        tooltipLines.push(`Policy: ${adaptivePolicyName}`);
      }
      layer.bindTooltip(
        tooltipLines.join('<br/>')
      );
    },
  }).addTo(map);

  const adaptiveToggle = document.getElementById('toggle-adaptive');
  function renderAdaptiveCells() {
    clearLayer(adaptiveLayer);
    if (!adaptiveToggle.checked) return;
    adaptiveLayer.addData(gbAdaptiveFeatures);
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
    if (e.target.checked) countryLayer.addData(gbCountryCells);
  });

  adaptiveToggle.addEventListener('change', () => {
    renderAdaptiveCells();
  });
}

init().catch((error) => {
  const node = document.getElementById('drilldown-content');
  node.textContent = `UI load error: ${error.message}`;
});
