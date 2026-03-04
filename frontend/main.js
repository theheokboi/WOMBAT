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

const DEFAULT_COUNTRY_CODE = 'GB';
const ADAPTIVE_MIN_RESOLUTION = 5;
const ADAPTIVE_MAX_RESOLUTION = 9;

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

function isAdaptiveResolutionAllowed(properties) {
  const raw = getAdaptiveResolution(properties);
  const resolution = Number(raw);
  if (!Number.isInteger(resolution)) return false;
  return resolution >= ADAPTIVE_MIN_RESOLUTION && resolution <= ADAPTIVE_MAX_RESOLUTION;
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

function getRequestedCountryCode() {
  const params = new URLSearchParams(window.location.search);
  return normalizeCountryCode(params.get('country')) || DEFAULT_COUNTRY_CODE;
}

function buildAvailableCountries(countryFeatures) {
  const countries = new Set();
  for (const feature of countryFeatures || []) {
    const code = normalizeCountryCode(feature?.properties?.layer_value);
    if (code) countries.add(code);
  }
  return Array.from(countries).sort();
}

function buildCountryCellIndex(countryFeatures) {
  const countryByMaskCell = new Map();
  for (const feature of countryFeatures || []) {
    const code = normalizeCountryCode(feature?.properties?.layer_value);
    const cell = feature?.properties?.h3;
    if (code && cell) {
      countryByMaskCell.set(String(cell), code);
    }
  }
  return countryByMaskCell;
}

function inferCountryCodeFromCell(cell, countryByMaskCell) {
  if (!cell || !countryByMaskCell || countryByMaskCell.size === 0 || !window.h3) return '';
  let cursor = String(cell);
  try {
    let resolution = h3.getResolution(cursor);
    while (resolution >= 0) {
      const code = countryByMaskCell.get(cursor);
      if (code) return code;
      if (resolution === 0) break;
      resolution -= 1;
      cursor = h3.cellToParent(cursor, resolution);
    }
  } catch (_error) {
    return '';
  }
  return '';
}

function getFeatureCountryCandidates(feature, countryByMaskCell, availableCountriesSet) {
  const properties = feature?.properties || {};
  const out = new Set();

  for (const rawCountry of [
    properties.layer_value,
    properties.country_code,
    properties.country,
    properties.country_iso,
    properties.country_iso2,
  ]) {
    const code = normalizeCountryCode(rawCountry);
    if (code && (!availableCountriesSet || availableCountriesSet.has(code))) out.add(code);
  }

  for (const cell of getFeatureH3Candidates(properties)) {
    const inferred = inferCountryCodeFromCell(cell, countryByMaskCell);
    if (inferred && (!availableCountriesSet || availableCountriesSet.has(inferred))) out.add(inferred);
  }

  return out;
}

function countFeaturesByCountry(features, countryByMaskCell, availableCountriesSet, predicate = null) {
  const counts = new Map();
  for (const feature of features || []) {
    if (predicate && !predicate(feature)) continue;
    const candidates = getFeatureCountryCandidates(feature, countryByMaskCell, availableCountriesSet);
    for (const code of candidates) {
      counts.set(code, (counts.get(code) || 0) + 1);
    }
  }
  return counts;
}

function filterFeaturesByCountry(features, countryCode, countryByMaskCell, availableCountriesSet, predicate = null) {
  return (features || []).filter((feature) => {
    if (predicate && !predicate(feature)) return false;
    return getFeatureCountryCandidates(feature, countryByMaskCell, availableCountriesSet).has(countryCode);
  });
}

function setupCountrySelector(availableCountries, requestedCountry, effectiveCountry) {
  const selector = document.getElementById('country-selector');
  if (!selector) return;
  const countryOptions = Array.from(new Set([...(availableCountries || []), requestedCountry].filter(Boolean))).sort();
  selector.innerHTML = '';
  for (const code of countryOptions) {
    const option = document.createElement('option');
    option.value = code;
    option.textContent = code;
    if (code === effectiveCountry) option.selected = true;
    selector.appendChild(option);
  }

  selector.disabled = countryOptions.length === 0;
  selector.title = `Requested: ${requestedCountry}; Effective: ${effectiveCountry}`;
  selector.addEventListener('change', () => {
    const params = new URLSearchParams(window.location.search);
    params.set('country', selector.value);
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}`;
    window.location.assign(nextUrl);
  });
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
  const requestedCountry = getRequestedCountryCode();
  const availableCountries = buildAvailableCountries(countryFeatures);
  const availableCountriesSet = new Set(availableCountries);
  const countryByMaskCell = buildCountryCellIndex(countryFeatures);

  const countryCountsByCode = new Map();
  for (const code of availableCountries) {
    countryCountsByCode.set(code, 0);
  }
  for (const feature of countryFeatures) {
    const code = normalizeCountryCode(feature?.properties?.layer_value);
    if (code) countryCountsByCode.set(code, (countryCountsByCode.get(code) || 0) + 1);
  }

  const facilitiesFeatures = featureCollectionFeatures(facilities);
  const adaptiveFeatures = featureCollectionFeatures(adaptiveCells);
  const facilityCountsByCode = countFeaturesByCountry(facilitiesFeatures, countryByMaskCell, availableCountriesSet);
  const adaptiveCountsByCode = countFeaturesByCountry(
    adaptiveFeatures,
    countryByMaskCell,
    availableCountriesSet,
    (feature) => isAdaptiveResolutionAllowed(feature?.properties || {})
  );

  function totalCountryDataCount(code) {
    return (
      (facilityCountsByCode.get(code) || 0) +
      (countryCountsByCode.get(code) || 0) +
      (adaptiveCountsByCode.get(code) || 0)
    );
  }

  let effectiveCountry = requestedCountry;
  let fallbackNotice = '';
  if (totalCountryDataCount(effectiveCountry) === 0) {
    const fallbackCandidate = availableCountries.find((code) => totalCountryDataCount(code) > 0)
      || availableCountries[0]
      || requestedCountry;
    if (fallbackCandidate !== requestedCountry) {
      fallbackNotice =
        `Fallback applied: requested ${requestedCountry} has zero data across facilities/country/adaptive; using ${fallbackCandidate}.`;
    }
    effectiveCountry = fallbackCandidate;
  }

  const effectiveCountryFeatures = countryFeatures.filter(
    (feature) => normalizeCountryCode(feature?.properties?.layer_value) === effectiveCountry
  );
  const effectiveFacilitiesFeatures = filterFeaturesByCountry(
    facilitiesFeatures,
    effectiveCountry,
    countryByMaskCell,
    availableCountriesSet
  );
  const effectiveAdaptiveFeatures = filterFeaturesByCountry(
    adaptiveFeatures,
    effectiveCountry,
    countryByMaskCell,
    availableCountriesSet,
    (feature) => isAdaptiveResolutionAllowed(feature?.properties || {})
  );
  const scopedFacilities = { ...facilities, features: effectiveFacilitiesFeatures };
  const scopedCountryCells = { ...countryCells, features: effectiveCountryFeatures };
  setupCountrySelector(availableCountries, requestedCountry, effectiveCountry);

  const adaptivePolicyName = adaptiveMetadata?.policy_name || adaptiveMetadata?.policy?.name || null;
  const policyVersion = adaptiveMetadata?.layer_version || latestStatus?.adaptive_policy?.layer_version || '--';

  const [lon, lat] = ui.center;
  document.getElementById('facility-count').textContent = `${effectiveCountry} facilities loaded: ${scopedFacilities.features.length.toLocaleString()}`;
  document.getElementById('location-count').textContent =
    `${effectiveCountry} unique locations: ${new Set((scopedFacilities.features || []).map((f) => f.geometry.coordinates.join(','))).size.toLocaleString()}`;
  const displayScopeNode = document.getElementById('display-scope');
  const latestAdaptiveVersionNode = document.getElementById('latest-adaptive-version');
  const adaptivePolicyNode = document.getElementById('adaptive-policy');
  const runtimeExpectationNode = document.getElementById('runtime-expectation');
  const latestRunRuntimeNode = document.getElementById('latest-run-runtime');
  const activeRunStatusNode = document.getElementById('active-run-status');
  const calibrationBasisNode = document.getElementById('calibration-basis');
  const availableCountriesPreview = availableCountries.slice(0, 12).join(', ');
  const availableCountriesLabel =
    availableCountries.length > 12 ? `${availableCountriesPreview}, ...` : (availableCountriesPreview || '--');
  const fallbackSuffix = fallbackNotice ? ` ${fallbackNotice}` : '';
  displayScopeNode.textContent =
    `Display scope: requested=${requestedCountry}, effective=${effectiveCountry}; available countries (${availableCountries.length}): ${availableCountriesLabel}; ` +
    `${effectiveCountryFeatures.length.toLocaleString()} country cells, ${effectiveAdaptiveFeatures.length.toLocaleString()} adaptive cells.${fallbackSuffix}`;

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
    facilityLayer.addData(scopedFacilities);
  }

  renderFacilities();

  const countryLayer = L.geoJSON(scopedCountryCells, {
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
    adaptiveLayer.addData(effectiveAdaptiveFeatures);
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
    if (e.target.checked) countryLayer.addData(scopedCountryCells);
  });

  adaptiveToggle.addEventListener('change', () => {
    renderAdaptiveCells();
  });
}

init().catch((error) => {
  const node = document.getElementById('drilldown-content');
  node.textContent = `UI load error: ${error.message}`;
});
