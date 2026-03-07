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

function parseIntegerOrDefault(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : fallback;
}

function buildAdaptiveResolutionBounds(adaptiveMetadata) {
  const params = adaptiveMetadata?.params || {};
  const min = parseIntegerOrDefault(params.min_output_resolution, 5);
  const max = parseIntegerOrDefault(params.facility_max_resolution, 9);
  if (min < 0 || max > 9 || min > max) return { min: 5, max: 9 };
  return { min, max };
}

function clearLayer(layer) {
  if (layer) layer.clearLayers();
}

function toNumeric(value) {
  if (value === null || value === undefined || value === '') return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

const FACILITY_POINT_COLOR = '#f97316';
const LANDING_POINT_COLOR = '#0ea5e9';
const OSM_TRANSPORT_STYLES = {
  rail: { color: '#374151', weight: 1.5, opacity: 0.9, dashArray: '7 4' },
  motorway: { color: '#dc2626', weight: 2.8, opacity: 0.95, dashArray: null },
  motorway_link: { color: '#ef4444', weight: 2.2, opacity: 0.9, dashArray: '6 3' },
  trunk: { color: '#ea580c', weight: 2.2, opacity: 0.95, dashArray: '10 3' },
  trunk_link: { color: '#f97316', weight: 1.8, opacity: 0.9, dashArray: '5 3' },
};
const OSM_GRAPH_EDGE_PALETTE = ['#e11d48', '#dc2626', '#ea580c', '#ca8a04', '#65a30d', '#16a34a', '#0891b2', '#2563eb', '#4f46e5', '#7c3aed', '#c026d3', '#db2777'];
const BASEMAP_STYLES = {
  positron: {
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    options: {
      maxZoom: 19,
      subdomains: 'abcd',
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    },
  },
  osm: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    },
  },
  dark: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    options: {
      maxZoom: 19,
      subdomains: 'abcd',
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    },
  },
};

function isLandingPointFeature(feature) {
  const source = String(feature?.properties?.source_name || '').toLowerCase();
  return source.includes('landing');
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

function isAdaptiveResolutionAllowed(properties, bounds) {
  const raw = getAdaptiveResolution(properties);
  const resolution = Number(raw);
  if (!Number.isInteger(resolution)) return false;
  return resolution >= bounds.min && resolution <= bounds.max;
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

function normalizeOsmTransportSource(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'graph' || normalized === 'shapefile') return normalized;
  return '';
}

function normalizeOsmGraphVariant(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'raw' || normalized === 'collapsed') return normalized;
  return '';
}

function getBackendPreferredOsmTransportSource(osmTransportResponse) {
  const candidates = [
    osmTransportResponse?.source,
    osmTransportResponse?.default_source,
    osmTransportResponse?.selected_source,
    osmTransportResponse?.metadata?.source,
    osmTransportResponse?.metadata?.default_source,
  ];
  for (const candidate of candidates) {
    const normalized = normalizeOsmTransportSource(candidate);
    if (normalized) return normalized;
  }
  return 'shapefile';
}

function getBackendPreferredOsmGraphVariant(osmTransportResponse) {
  const candidates = [
    osmTransportResponse?.graph_variant,
    osmTransportResponse?.default_graph_variant,
    osmTransportResponse?.selected_graph_variant,
    osmTransportResponse?.metadata?.graph_variant,
    osmTransportResponse?.metadata?.default_graph_variant,
  ];
  for (const candidate of candidates) {
    const normalized = normalizeOsmGraphVariant(candidate);
    if (normalized) return normalized;
  }
  return 'raw';
}

function buildOsmTransportPath(source, includeNodes = false, graphVariant = 'raw') {
  const url = new URL('/v1/osm/transport', window.location.origin);
  const selectedSource = normalizeOsmTransportSource(source) || 'shapefile';
  url.searchParams.set('source', selectedSource);
  if (selectedSource === 'graph') {
    url.searchParams.set('graph_variant', normalizeOsmGraphVariant(graphVariant) || 'raw');
  }
  if (includeNodes) url.searchParams.set('include_nodes', 'true');
  return `${url.pathname}?${url.searchParams.toString()}`;
}

function getGeometryType(feature) {
  return String(feature?.geometry?.type || '').toLowerCase();
}

function isGraphEdgeFeature(feature) {
  const featureType = String(feature?.properties?.graph_feature_type || '').toLowerCase();
  if (featureType === 'edge') return true;
  const geometryType = getGeometryType(feature);
  return geometryType.includes('line');
}

function isGraphNodeFeature(feature) {
  const featureType = String(feature?.properties?.graph_feature_type || '').toLowerCase();
  if (featureType === 'node') return true;
  return getGeometryType(feature) === 'point';
}

function getGraphEdgeKey(feature, fallbackIndex) {
  const edgeId = feature?.properties?.edge_id;
  if (edgeId) return String(edgeId);
  return `edge_${fallbackIndex}`;
}

function getGraphNodeId(raw) {
  if (raw === null || raw === undefined) return '';
  return String(raw).trim();
}

function colorGraphEdgesByAdjacency(features) {
  const graphEdges = [];
  for (const feature of features || []) {
    if (isGraphEdgeFeature(feature)) graphEdges.push(feature);
  }
  if (graphEdges.length === 0) return;

  const edgeRecords = graphEdges.map((feature, index) => {
    const p = feature?.properties || {};
    const u = getGraphNodeId(p.u);
    const v = getGraphNodeId(p.v);
    return {
      feature,
      key: getGraphEdgeKey(feature, index),
      u,
      v,
    };
  });

  const incident = new Map();
  for (const record of edgeRecords) {
    if (!record.u || !record.v) continue;
    if (!incident.has(record.u)) incident.set(record.u, []);
    if (!incident.has(record.v)) incident.set(record.v, []);
    incident.get(record.u).push(record.key);
    incident.get(record.v).push(record.key);
  }

  const recordByKey = new Map(edgeRecords.map((record) => [record.key, record]));
  const order = [...edgeRecords].sort((a, b) => {
    const aDegree = (incident.get(a.u)?.length || 0) + (incident.get(a.v)?.length || 0);
    const bDegree = (incident.get(b.u)?.length || 0) + (incident.get(b.v)?.length || 0);
    return bDegree - aDegree;
  });

  const assigned = new Map();
  for (const record of order) {
    const used = new Set();
    for (const nodeId of [record.u, record.v]) {
      const neighbors = incident.get(nodeId) || [];
      for (const neighborKey of neighbors) {
        const neighborColor = assigned.get(neighborKey);
        if (neighborColor !== undefined) used.add(neighborColor);
      }
    }
    let colorIndex = 0;
    while (used.has(colorIndex) && colorIndex < OSM_GRAPH_EDGE_PALETTE.length) {
      colorIndex += 1;
    }
    if (colorIndex >= OSM_GRAPH_EDGE_PALETTE.length) {
      colorIndex = Math.abs(record.key.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)) % OSM_GRAPH_EDGE_PALETTE.length;
    }
    assigned.set(record.key, colorIndex);
  }

  for (const [key, colorIndex] of assigned.entries()) {
    const record = recordByKey.get(key);
    if (!record || !record.feature || !record.feature.properties) continue;
    record.feature.properties.edge_palette_index = colorIndex;
    record.feature.properties.edge_palette_color = OSM_GRAPH_EDGE_PALETTE[colorIndex];
  }
}

function normalizeCountryCode(value) {
  if (value === null || value === undefined) return '';
  const normalized = String(value).trim().toUpperCase();
  if (normalized.length === 2) return normalized;
  return '';
}

function normalizeRunId(value) {
  if (value === null || value === undefined) return '';
  return String(value).trim();
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

function getRequestedRunId() {
  const params = new URLSearchParams(window.location.search);
  return normalizeRunId(params.get('run'));
}

function buildRunLabel(run) {
  const runId = normalizeRunId(run?.run_id) || '--';
  const mode = run?.country_mask_mode ? String(run.country_mask_mode) : '--';
  const resolution = Number.isInteger(Number(run?.country_mask_resolution))
    ? `r${Number(run.country_mask_resolution)}`
    : '--';
  return `${resolution} | ${mode} | ${runId}`;
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

function setupRunSelector(runCatalog, requestedRunId, effectiveRunId) {
  const selector = document.getElementById('run-selector');
  if (!selector) return;
  const runs = Array.isArray(runCatalog?.runs) ? runCatalog.runs : [];
  selector.innerHTML = '';
  for (const run of runs) {
    const runId = normalizeRunId(run?.run_id);
    if (!runId) continue;
    const option = document.createElement('option');
    option.value = runId;
    option.textContent = buildRunLabel(run);
    if (runId === effectiveRunId) option.selected = true;
    selector.appendChild(option);
  }

  selector.disabled = runs.length === 0;
  selector.title = `Requested: ${requestedRunId || '--'}; Effective: ${effectiveRunId || '--'}`;
  selector.addEventListener('change', () => {
    const params = new URLSearchParams(window.location.search);
    params.set('run', selector.value);
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}`;
    window.location.assign(nextUrl);
  });
}

async function init() {
  const [ui, runCatalog] = await Promise.all([
    loadJson('/v1/ui/config'),
    tryLoadJson('/v1/runs/catalog'),
  ]);
  const requestedRunId = getRequestedRunId();
  const runs = Array.isArray(runCatalog?.runs) ? runCatalog.runs : [];
  const runIdSet = new Set(runs.map((run) => normalizeRunId(run?.run_id)).filter(Boolean));
  const latestCatalogRunId = normalizeRunId(runCatalog?.latest_run_id);
  let effectiveRunId = requestedRunId;
  if (!effectiveRunId || !runIdSet.has(effectiveRunId)) {
    effectiveRunId = latestCatalogRunId || (runs[0] ? normalizeRunId(runs[0].run_id) : '');
  }
  setupRunSelector(runCatalog, requestedRunId, effectiveRunId);

  const withRun = (path) => {
    if (!effectiveRunId) return path;
    const url = new URL(path, window.location.origin);
    url.searchParams.set('run_id', effectiveRunId);
    return `${url.pathname}?${url.searchParams.toString()}`;
  };

  const [facilities, countryCells, adaptiveCells, adaptiveMetadata, runStatus, activeStatus, calibrationLatest, osmTransport] = await Promise.all([
    loadJson(withRun('/v1/facilities?limit=50000')),
    loadJson(withRun('/v1/layers/country_mask/cells')),
    loadJson(withRun('/v1/layers/facility_density_adaptive/cells?limit=100000')),
    tryLoadJson(withRun('/v1/layers/facility_density_adaptive/metadata')),
    effectiveRunId ? tryLoadJson(`/v1/runs/${encodeURIComponent(effectiveRunId)}/status`) : tryLoadJson('/v1/runs/latest/status'),
    tryLoadJson('/v1/runs/active/status'),
    tryLoadJson('/v1/calibration/latest'),
    tryLoadJson('/v1/osm/transport'),
  ]);
  const countryFeatures = featureCollectionFeatures(countryCells);
  const availableCountries = buildAvailableCountries(countryFeatures);
  const adaptiveResolutionBounds = buildAdaptiveResolutionBounds(adaptiveMetadata);

  const facilitiesFeatures = featureCollectionFeatures(facilities);
  const adaptiveFeatures = featureCollectionFeatures(adaptiveCells);
  let osmTransportEdgeFeatures = [];
  let osmTransportNodeFeatures = [];
  const effectiveAdaptiveFeatures = (adaptiveFeatures || []).filter(
    (feature) => isAdaptiveResolutionAllowed(feature?.properties || {}, adaptiveResolutionBounds)
  );
  const scopedFacilities = facilities;
  const scopedCountryCells = countryCells;

  const adaptivePolicyName = adaptiveMetadata?.policy_name || adaptiveMetadata?.policy?.name || null;
  const policyVersion = adaptiveMetadata?.layer_version || runStatus?.adaptive_policy?.layer_version || '--';

  const [lon, lat] = ui.center;
  document.getElementById('facility-count').textContent = `All-country facilities loaded: ${scopedFacilities.features.length.toLocaleString()}`;
  document.getElementById('location-count').textContent =
    `All-country unique locations: ${new Set((scopedFacilities.features || []).map((f) => f.geometry.coordinates.join(','))).size.toLocaleString()}`;
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
  displayScopeNode.textContent =
    `Display scope: run=${effectiveRunId || '--'}; mode=all-countries; available countries (${availableCountries.length}): ${availableCountriesLabel}; ` +
    `${featureCollectionFeatures(scopedCountryCells).length.toLocaleString()} country cells, ${effectiveAdaptiveFeatures.length.toLocaleString()} adaptive cells.`;

  const latestRunId = runStatus?.run_id || effectiveRunId || '--';
  const latestPolicyName = runStatus?.adaptive_policy?.policy_name || adaptivePolicyName || '--';
  const latestPolicyVersion = runStatus?.adaptive_policy?.layer_version || policyVersion || '--';
  latestAdaptiveVersionNode.textContent =
    `Selected run adaptive version: ${latestRunId} | ${latestPolicyName} | ${latestPolicyVersion}`;

  adaptivePolicyNode.textContent = `Adaptive policy: ${adaptivePolicyName || '--'} (${policyVersion})`;

  const makeRunTypical = runStatus?.runtime_expectations?.make_run?.typical_minutes || '--';
  const makeRunSlow = runStatus?.runtime_expectations?.make_run?.slow_path_minutes || '--';
  runtimeExpectationNode.textContent = `Runtime expectation: make run typical ${makeRunTypical} min, slow path ${makeRunSlow} min`;

  const latestRuntimeSeconds = runStatus?.metrics?.run_duration_seconds;
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
  const basemapSelector = document.getElementById('basemap-selector');
  const createBasemapLayer = (basemapId) => {
    const id = BASEMAP_STYLES[basemapId] ? basemapId : 'positron';
    const style = BASEMAP_STYLES[id];
    return L.tileLayer(style.url, style.options);
  };
  let currentBasemap = 'positron';
  let basemapLayer = createBasemapLayer(currentBasemap).addTo(map);
  if (basemapSelector) {
    basemapSelector.value = currentBasemap;
    basemapSelector.addEventListener('change', () => {
      const nextBasemap = BASEMAP_STYLES[basemapSelector.value] ? basemapSelector.value : 'positron';
      if (nextBasemap === currentBasemap) return;
      if (basemapLayer) map.removeLayer(basemapLayer);
      basemapLayer = createBasemapLayer(nextBasemap).addTo(map);
      currentBasemap = nextBasemap;
    });
  }

  const facilityLayer = L.geoJSON(null, {
    pointToLayer: (feature, latlng) => {
      const p = feature.properties || {};
      const radius = p.facility_count
        ? Math.min(12, 2 + Math.log10(Math.max(1, Number(p.facility_count))) * 3)
        : 3;
      const fillColor = isLandingPointFeature(feature) ? LANDING_POINT_COLOR : FACILITY_POINT_COLOR;
      return L.circleMarker(latlng, {
        radius,
        color: '#ffffff',
        weight: 1,
        fillColor,
        fillOpacity: 0.95,
      });
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const pointType = isLandingPointFeature(feature) ? 'Landing point' : 'Facility';
      layer.bindTooltip(
        `Type: ${pointType}<br/>` +
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

  const osmTransportEdgeLayer = L.geoJSON(null, {
    style: (feature) => {
      const edgeColor = feature?.properties?.edge_palette_color;
      if (edgeColor) {
        return {
          color: edgeColor,
          weight: 2.4,
          opacity: 0.92,
          dashArray: null,
        };
      }
      const transportClass =
        String(feature?.properties?.transport_class || feature?.properties?.infrastructure_type || '').toLowerCase();
      const style = OSM_TRANSPORT_STYLES[transportClass] || OSM_TRANSPORT_STYLES.trunk;
      return {
        color: style.color,
        weight: style.weight,
        opacity: style.opacity,
        dashArray: style.dashArray || null,
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const transportClass = String(p.transport_class || p.infrastructure_type || '').toLowerCase();
      layer.bindTooltip(
        `Layer: osm_transport<br/>Class: ${transportClass || '--'}<br/>Country: ${p.country_code || '--'}`
      );
    },
  }).addTo(map);
  const osmTransportNodeLayer = L.geoJSON(null, {
    pointToLayer: (_feature, latlng) =>
      L.circleMarker(latlng, {
        radius: 2.8,
        color: '#0f172a',
        weight: 1,
        fillColor: '#f8fafc',
        fillOpacity: 0.95,
      }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      layer.bindTooltip(
        `Layer: osm_transport_graph_node<br/>Node ID: ${p.node_id ?? '--'}<br/>Country: ${p.country_code || '--'}`
      );
    },
  }).addTo(map);

  const osmTransportToggle = document.getElementById('toggle-osm-transport');
  const osmTransportSourceSelect = document.getElementById('osm-transport-source');
  const osmGraphVariantControl = document.getElementById('osm-graph-variant-control');
  const osmGraphVariantSelect = document.getElementById('osm-graph-variant');
  let selectedOsmTransportSource = getBackendPreferredOsmTransportSource(osmTransport);
  let selectedOsmGraphVariant = getBackendPreferredOsmGraphVariant(osmTransport);
  if (osmTransportSourceSelect) {
    osmTransportSourceSelect.value = selectedOsmTransportSource;
    if (osmTransportSourceSelect.value !== selectedOsmTransportSource) {
      selectedOsmTransportSource = 'shapefile';
      osmTransportSourceSelect.value = selectedOsmTransportSource;
    }
  }
  if (osmGraphVariantSelect) {
    osmGraphVariantSelect.value = selectedOsmGraphVariant;
    if (osmGraphVariantSelect.value !== selectedOsmGraphVariant) {
      selectedOsmGraphVariant = 'raw';
      osmGraphVariantSelect.value = selectedOsmGraphVariant;
    }
  }

  function syncOsmGraphVariantControl() {
    const isGraphSource = selectedOsmTransportSource === 'graph';
    if (osmGraphVariantControl) osmGraphVariantControl.hidden = !isGraphSource;
    if (osmGraphVariantSelect) osmGraphVariantSelect.disabled = !isGraphSource;
  }

  function renderOsmTransport() {
    clearLayer(osmTransportEdgeLayer);
    clearLayer(osmTransportNodeLayer);
    if (!osmTransportToggle || !osmTransportToggle.checked) return;
    osmTransportEdgeLayer.addData(osmTransportEdgeFeatures);
    osmTransportNodeLayer.addData(osmTransportNodeFeatures);
  }

  async function reloadOsmTransport() {
    const selectedSource = normalizeOsmTransportSource(selectedOsmTransportSource) || 'shapefile';
    const selectedVariant = normalizeOsmGraphVariant(selectedOsmGraphVariant) || 'raw';
    const includeNodes = selectedSource === 'graph';
    const payload = await tryLoadJson(buildOsmTransportPath(selectedSource, includeNodes, selectedVariant));
    const features = featureCollectionFeatures(payload);
    if (selectedSource === 'graph') {
      colorGraphEdgesByAdjacency(features);
      osmTransportEdgeFeatures = features.filter((feature) => isGraphEdgeFeature(feature));
      osmTransportNodeFeatures = features.filter((feature) => isGraphNodeFeature(feature));
    } else {
      osmTransportEdgeFeatures = features;
      osmTransportNodeFeatures = [];
    }
    renderOsmTransport();
  }
  syncOsmGraphVariantControl();
  await reloadOsmTransport();

  const combined = L.featureGroup([facilityLayer, countryLayer, adaptiveLayer, osmTransportEdgeLayer, osmTransportNodeLayer]);
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
  if (osmTransportToggle) {
    osmTransportToggle.addEventListener('change', () => {
      renderOsmTransport();
    });
  }
  if (osmTransportSourceSelect) {
    osmTransportSourceSelect.addEventListener('change', async () => {
      selectedOsmTransportSource = normalizeOsmTransportSource(osmTransportSourceSelect.value) || 'shapefile';
      syncOsmGraphVariantControl();
      await reloadOsmTransport();
    });
  }
  if (osmGraphVariantSelect) {
    osmGraphVariantSelect.addEventListener('change', async () => {
      selectedOsmGraphVariant = normalizeOsmGraphVariant(osmGraphVariantSelect.value) || 'raw';
      if (selectedOsmTransportSource !== 'graph') return;
      await reloadOsmTransport();
    });
  }
}

init().catch((error) => {
  const node = document.getElementById('drilldown-content');
  node.textContent = `UI load error: ${error.message}`;
});
