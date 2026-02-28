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

async function init() {
  const [ui, facilities, countryCells, adaptiveCells, adaptiveMetadata, latestStatus, activeStatus, calibrationLatest, calibrationWorldEstimate] = await Promise.all([
    loadJson('/v1/ui/config'),
    loadJson('/v1/facilities?limit=50000'),
    loadJson('/v1/layers/country_mask/cells'),
    loadJson('/v1/layers/facility_density_adaptive/cells?limit=100000'),
    tryLoadJson('/v1/layers/facility_density_adaptive/metadata'),
    tryLoadJson('/v1/runs/latest/status'),
    tryLoadJson('/v1/runs/active/status'),
    tryLoadJson('/v1/calibration/latest'),
    tryLoadJson('/v1/calibration/estimates/world'),
  ]);
  const adaptiveFeatures = featureCollectionFeatures(adaptiveCells);
  const adaptivePolicyName = adaptiveMetadata?.policy_name || adaptiveMetadata?.policy?.name || null;
  const policyVersion = adaptiveMetadata?.layer_version || latestStatus?.adaptive_policy?.layer_version || '--';

  const [lon, lat] = ui.center;
  document.getElementById('facility-count').textContent = `Facilities loaded: ${facilities.features.length.toLocaleString()}`;
  document.getElementById('location-count').textContent = `Unique locations: ${new Set((facilities.features || []).map((f) => f.geometry.coordinates.join(','))).size.toLocaleString()}`;
  const adaptivePolicyNode = document.getElementById('adaptive-policy');
  const runtimeExpectationNode = document.getElementById('runtime-expectation');
  const latestRunRuntimeNode = document.getElementById('latest-run-runtime');
  const activeRunStatusNode = document.getElementById('active-run-status');
  const calibrationBasisNode = document.getElementById('calibration-basis');
  const calibrationWorldEstimateNode = document.getElementById('calibration-world-estimate');

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

  if (calibrationWorldEstimate) {
    const estimate = calibrationWorldEstimate.estimate || {};
    const typicalMin = estimate.estimated_seconds_typical_min;
    const typicalMax = estimate.estimated_seconds_typical_max;
    const slowMax = estimate.estimated_seconds_slow_path_max;
    if (typeof typicalMin === 'number' && typeof typicalMax === 'number') {
      const slowLabel = typeof slowMax === 'number' ? `, slow path ${(slowMax / 60).toFixed(2)} min` : '';
      calibrationWorldEstimateNode.textContent =
        `World runtime estimate: typical ${(typicalMin / 60).toFixed(2)}-${(typicalMax / 60).toFixed(2)} min${slowLabel}`;
    } else {
      calibrationWorldEstimateNode.textContent = 'World runtime estimate: unavailable';
    }
  } else {
    calibrationWorldEstimateNode.textContent = 'World runtime estimate: unavailable';
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
    adaptiveLayer.addData(adaptiveFeatures);
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
