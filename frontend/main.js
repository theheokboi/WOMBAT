const {
  detectDataSource,
  loadJson,
  tryLoadJson,
} = window.inframapShared;
const {
  buildAdaptiveControlValueFromThreshold,
  buildAdaptiveCurrentScores,
  buildAdaptiveScoreModel,
  buildAdaptiveScoreScale,
  buildAdaptiveThresholdFromControl,
  clampNumber,
  formatScoreValue,
  interpolateColorStops,
  scoreToDisplayValue,
  smoothAnalysisMasses,
} = window.inframapAdaptiveScore;

function buildStaticRouteCountries(staticManifest) {
  const routeCountries = Array.isArray(staticManifest?.route_countries) ? staticManifest.route_countries : [];
  const normalized = routeCountries.map((value) => normalizeCountryCode(value)).filter(Boolean);
  return normalized.length > 0 ? normalized : ['AR', 'TW'];
}

function createDataSource({ mode, staticManifest, liveUiConfig }) {
  const routeCountries = buildStaticRouteCountries(staticManifest);
  if (mode === 'static') {
    return {
      mode,
      routeCountries,
      loadUiConfig: async () => loadJson('demo-data/ui-config.json'),
      loadRunsCatalog: async () => loadJson('demo-data/runs-catalog.json'),
      loadFacilities: async () => loadJson('demo-data/facilities.json'),
      loadCountryCells: async () => loadJson('demo-data/country-mask-cells.json'),
      loadAdaptiveCells: async () => loadJson('demo-data/facility-density-adaptive-cells.json'),
      loadR7RegionCells: async () => loadJson('demo-data/facility-density-r7-regions-cells.json'),
      loadAdaptiveMetadata: async () => tryLoadJson('demo-data/facility-density-adaptive-metadata.json'),
      loadRunStatus: async (_runId) => tryLoadJson('demo-data/run-status.json'),
      loadActiveStatus: async () => tryLoadJson('demo-data/active-status.json'),
      loadCalibrationLatest: async () => tryLoadJson('demo-data/calibration-latest.json'),
      loadR7RouteOverlay: async () => {
        const collections = await Promise.all(
          routeCountries.map((country) => tryLoadJson(`demo-data/r7-region-routes-${country}.json`))
        );
        return {
          type: 'FeatureCollection',
          features: collections.flatMap((collection) => featureCollectionFeatures(collection)),
        };
      },
    };
  }
  return {
    mode,
    routeCountries,
    loadUiConfig: async () => liveUiConfig || loadJson('/v1/ui/config'),
    loadRunsCatalog: async () => tryLoadJson('/v1/runs/catalog'),
    loadFacilities: async (runId) => {
      const url = new URL('/v1/facilities?limit=50000', window.location.origin);
      if (runId) url.searchParams.set('run_id', runId);
      return loadJson(`${url.pathname}?${url.searchParams.toString()}`);
    },
    loadCountryCells: async (runId) => {
      const url = new URL('/v1/layers/country_mask/cells', window.location.origin);
      if (runId) url.searchParams.set('run_id', runId);
      return loadJson(`${url.pathname}?${url.searchParams.toString()}`);
    },
    loadAdaptiveCells: async (runId) => {
      const url = new URL('/v1/layers/facility_density_adaptive/cells?limit=100000', window.location.origin);
      if (runId) url.searchParams.set('run_id', runId);
      return loadJson(`${url.pathname}?${url.searchParams.toString()}`);
    },
    loadR7RegionCells: async (runId) => {
      const url = new URL('/v1/layers/facility_density_r7_regions/cells?limit=200000', window.location.origin);
      if (runId) url.searchParams.set('run_id', runId);
      return loadJson(`${url.pathname}?${url.searchParams.toString()}`);
    },
    loadAdaptiveMetadata: async (runId) => {
      const url = new URL('/v1/layers/facility_density_adaptive/metadata', window.location.origin);
      if (runId) url.searchParams.set('run_id', runId);
      return tryLoadJson(`${url.pathname}?${url.searchParams.toString()}`);
    },
    loadRunStatus: async (runId) => (
      runId
        ? tryLoadJson(`/v1/runs/${encodeURIComponent(runId)}/status`)
        : tryLoadJson('/v1/runs/latest/status')
    ),
    loadActiveStatus: async () => tryLoadJson('/v1/runs/active/status'),
    loadCalibrationLatest: async () => tryLoadJson('/v1/calibration/latest'),
    loadR7RouteOverlay: async () => {
      const collections = await Promise.all(
        routeCountries.map((country) => tryLoadJson(`/v1/r7-region-routes?country=${country}`))
      );
      return {
        type: 'FeatureCollection',
        features: collections.flatMap((collection) => featureCollectionFeatures(collection)),
      };
    },
  };
}

function parseIntegerOrDefault(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : fallback;
}

function formatResolutionTag(value) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) return '--';
  return `r${parsed}`;
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
const BASEMAP_STYLES = {
  positron: {
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    options: {
      maxZoom: 19,
      subdomains: 'abcd',
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
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

function getRegionClusterId(properties) {
  if (!properties) return '';
  if (properties.cluster_id) return String(properties.cluster_id);
  return '';
}

function hashString(value) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

const R7_REGION_COLORS = ['#0f766e', '#1d4ed8', '#7c3aed', '#b45309', '#be123c', '#4338ca'];
const R7_ROUTE_COLORS = {
  AR: '#dc2626',
  TW: '#0891b2',
};

function getRegionClusterColor(clusterId) {
  if (!clusterId) return R7_REGION_COLORS[0];
  return R7_REGION_COLORS[hashString(clusterId) % R7_REGION_COLORS.length];
}

function getR7RouteColor(countryCode) {
  const normalized = normalizeCountryCode(countryCode);
  return R7_ROUTE_COLORS[normalized] || '#475569';
}

function formatDistanceKm(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '--';
  return `${(numeric / 1000).toFixed(1)} km`;
}

function formatDurationMinutes(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '--';
  return `${(numeric / 60).toFixed(1)} min`;
}

function buildUniqueR7RegionMarkers(features) {
  const byCluster = new Map();
  for (const feature of features || []) {
    const p = feature?.properties || {};
    const clusterId = getRegionClusterId(p);
    const lat = Number(p.region_lat);
    const lon = Number(p.region_lon);
    if (!clusterId || !Number.isFinite(lat) || !Number.isFinite(lon) || byCluster.has(clusterId)) continue;
    byCluster.set(clusterId, {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [lon, lat],
      },
      properties: {
        ...p,
      },
    });
  }
  return Array.from(byCluster.values()).sort((a, b) => String(a.properties.cluster_id).localeCompare(String(b.properties.cluster_id)));
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

function makeH3PolygonFeature(cell, baseProperties = {}) {
  const boundary = h3.cellToBoundary(String(cell));
  const ring = boundary.map(([lat, lon]) => [lon, lat]);
  if (ring.length > 0) {
    const first = ring[0];
    const last = ring[ring.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) ring.push([first[0], first[1]]);
  }
  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [ring],
    },
    properties: {
      ...baseProperties,
      h3: String(cell),
      resolution: h3.getResolution(String(cell)),
    },
  };
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
  const detectedDataSource = await detectDataSource();
  const dataSource = createDataSource(detectedDataSource);
  const [ui, runCatalog] = await Promise.all([
    dataSource.loadUiConfig(),
    dataSource.loadRunsCatalog(),
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

  const [facilities, countryCells, adaptiveCells, r7RegionCells, adaptiveMetadata, runStatus, activeStatus, calibrationLatest] = await Promise.all([
    dataSource.loadFacilities(effectiveRunId),
    dataSource.loadCountryCells(effectiveRunId),
    dataSource.loadAdaptiveCells(effectiveRunId),
    dataSource.loadR7RegionCells(effectiveRunId),
    dataSource.loadAdaptiveMetadata(effectiveRunId),
    dataSource.loadRunStatus(effectiveRunId),
    dataSource.loadActiveStatus(),
    dataSource.loadCalibrationLatest(),
  ]);
  const countryFeatures = featureCollectionFeatures(countryCells);
  const availableCountries = buildAvailableCountries(countryFeatures);
  const adaptiveResolutionBounds = buildAdaptiveResolutionBounds(adaptiveMetadata);

  const adaptiveFeatures = featureCollectionFeatures(adaptiveCells);
  const r7RegionFeatures = featureCollectionFeatures(r7RegionCells);
  const r7RegionMarkerFeatures = buildUniqueR7RegionMarkers(r7RegionFeatures);
  const effectiveAdaptiveFeatures = (adaptiveFeatures || []).filter(
    (feature) => isAdaptiveResolutionAllowed(feature?.properties || {}, adaptiveResolutionBounds)
  );
  const adaptiveScoreModel = buildAdaptiveScoreModel(effectiveAdaptiveFeatures, adaptiveMetadata);
  const adaptiveScoreCache = new Map();
  const scopedFacilities = facilities;
  const scopedCountryCells = countryCells;
  let r7RouteOverlay = null;
  let r7RouteOverlayPromise = null;

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
  const adaptiveScoreModeLabelNode = document.getElementById('adaptive-score-mode-label');
  const adaptiveScoreLambdaValueNode = document.getElementById('adaptive-score-lambda-value');
  const adaptiveScoreIterationsValueNode = document.getElementById('adaptive-score-iterations-value');
  const adaptiveScoreThresholdValueNode = document.getElementById('adaptive-score-threshold-value');
  const adaptiveScoreRangeNode = document.getElementById('adaptive-score-range');
  const adaptiveScoreLegendMinNode = document.getElementById('adaptive-score-legend-min');
  const adaptiveScoreLegendMaxNode = document.getElementById('adaptive-score-legend-max');
  const adaptiveScoreLegendSubtitleNode = document.getElementById('adaptive-score-legend-subtitle');
  const availableCountriesPreview = availableCountries.slice(0, 12).join(', ');
  const availableCountriesLabel =
    availableCountries.length > 12 ? `${availableCountriesPreview}, ...` : (availableCountriesPreview || '--');
  displayScopeNode.textContent =
    `Display scope: run=${effectiveRunId || '--'}; source=${dataSource.mode}; mode=all-countries; available countries (${availableCountries.length}): ${availableCountriesLabel}; ` +
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

  const adaptiveScoreControls = {
    mode: document.getElementById('score-mode-raw')?.checked ? 'raw' : 'smoothed',
    lambda: clampNumber(Number(document.getElementById('score-lambda')?.value || 0.5), 0, 1),
    iterations: clampNumber(Number(document.getElementById('score-iterations')?.value || 1), 1, 3),
    threshold: 0,
  };
  adaptiveScoreControls.threshold = 0.5 * Math.max(0, Array.from(adaptiveScoreModel.rawScores.values()).reduce((max, value) => Math.max(max, value), 0));

  const adaptiveScoreState = {
    mode: adaptiveScoreControls.mode,
    lambda: adaptiveScoreControls.lambda,
    iterations: adaptiveScoreControls.iterations,
    threshold: adaptiveScoreControls.threshold,
    currentScores: new Map(),
    rawScores: new Map(adaptiveScoreModel.rawScores),
    smoothedScores: new Map(),
    currentMin: 0,
    currentMax: 0,
    scoreMaxForDisplay: 0,
  };
  let adaptiveThresholdInitialized = false;

  function getAdaptiveSmoothedAnalysisMasses(lambdaValue, iterations) {
    const cacheKey = `${lambdaValue.toFixed(2)}|${iterations}`;
    if (adaptiveScoreCache.has(cacheKey)) return adaptiveScoreCache.get(cacheKey);
    const baseMasses = adaptiveScoreModel.analysisCells.map((cell) => adaptiveScoreModel.analysisMasses.get(cell) || 0);
    const smoothed = smoothAnalysisMasses(baseMasses, adaptiveScoreModel.analysisNeighbors, lambdaValue, iterations);
    adaptiveScoreCache.set(cacheKey, smoothed);
    return smoothed;
  }

  function updateAdaptiveScoreControls(currentRange) {
    if (adaptiveScoreModeLabelNode) {
      adaptiveScoreModeLabelNode.textContent = adaptiveScoreState.mode === 'raw' ? 'Raw score' : 'Smoothed score';
    }
    if (adaptiveScoreLambdaValueNode) {
      adaptiveScoreLambdaValueNode.textContent = adaptiveScoreState.lambda.toFixed(2);
    }
    if (adaptiveScoreIterationsValueNode) {
      adaptiveScoreIterationsValueNode.textContent = String(adaptiveScoreState.iterations);
    }
    if (adaptiveScoreLegendSubtitleNode) {
      adaptiveScoreLegendSubtitleNode.textContent = `View range updates as the adaptive field changes`;
    }
    if (adaptiveScoreRangeNode) {
      adaptiveScoreRangeNode.textContent = `${formatScoreValue(currentRange.min)} / ${formatScoreValue(currentRange.max)}`;
    }
    if (adaptiveScoreLegendMinNode) {
      adaptiveScoreLegendMinNode.textContent = formatScoreValue(currentRange.min);
    }
    if (adaptiveScoreLegendMaxNode) {
      adaptiveScoreLegendMaxNode.textContent = formatScoreValue(currentRange.max);
    }
    if (adaptiveScoreThresholdValueNode) {
      adaptiveScoreThresholdValueNode.textContent = formatScoreValue(adaptiveScoreState.threshold);
    }
    const thresholdControl = document.getElementById('score-threshold');
    if (thresholdControl) {
      const maxDisplayValue = scoreToDisplayValue(currentRange.max);
      thresholdControl.max = String(Number.isFinite(maxDisplayValue) && maxDisplayValue > 0 ? maxDisplayValue : 1);
      const nextValue = clampNumber(buildAdaptiveControlValueFromThreshold(adaptiveScoreState.threshold), 0, Number(thresholdControl.max));
      thresholdControl.value = String(nextValue);
    }
  }

  function computeAdaptiveViewScores() {
    if (adaptiveScoreState.mode === 'raw') {
      const currentScores = new Map(adaptiveScoreModel.rawScores);
      const scale = buildAdaptiveScoreScale(currentScores);
      return {
        currentScores,
        currentMin: scale.min,
        currentMax: scale.max,
        rawScores: new Map(currentScores),
        smoothedScores: null,
      };
    }

    const smoothedAnalysisMasses = getAdaptiveSmoothedAnalysisMasses(adaptiveScoreState.lambda, adaptiveScoreState.iterations);
    const current = buildAdaptiveCurrentScores(adaptiveScoreModel, smoothedAnalysisMasses);
    const currentScale = buildAdaptiveScoreScale(current.smoothedScoresByOriginal);
    return {
      currentScores: current.smoothedScoresByOriginal,
      currentMin: currentScale.min,
      currentMax: currentScale.max,
      rawScores: current.rawScoresByOriginal,
      smoothedScores: current.smoothedScoresByOriginal,
    };
  }

function getAdaptiveFillColor(score, maxScore) {
  const normalized = maxScore > 0 ? scoreToDisplayValue(score) / Math.max(scoreToDisplayValue(maxScore), 1e-9) : 0;
  return interpolateColorStops(['#ffedd5', '#fdba74', '#fb923c', '#ea580c', '#9a3412'], normalized);
}

  const map = L.map('map', {
    center: [lat, lon],
    zoom: ui.zoom,
    preferCanvas: true,
    zoomControl: true,
  });
  window.__inframapMap = map;
  window.__inframapAdaptiveFeatures = effectiveAdaptiveFeatures;
  window.__inframapAdaptiveScoreState = adaptiveScoreState;

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
  const facilityToggle = document.getElementById('toggle-facilities');
  function renderFacilities() {
    clearLayer(facilityLayer);
    if (!facilityToggle || !facilityToggle.checked) return;
    facilityLayer.addData(scopedFacilities);
  }
  renderFacilities();

  const countryLayer = L.geoJSON(null, {
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
      const cellResolution = formatResolutionTag(p.resolution);
      layer.bindTooltip(
        `Layer: country_mask<br/>Country: ${p.layer_value || ''}<br/>Color: ${p.country_color ?? ''}<br/>H3: ${p.h3 || ''}` +
        `<br/>Cell resolution: ${cellResolution}`
      );
    },
  }).addTo(map);
  const countryToggle = document.getElementById('toggle-country');
  function renderCountryCells() {
    clearLayer(countryLayer);
    if (!countryToggle || !countryToggle.checked) return;
    countryLayer.addData(scopedCountryCells);
  }
  renderCountryCells();

  const adaptiveLayer = L.geoJSON(null, {
    style: (feature) => {
      const h3Index = getAdaptiveH3(feature?.properties || {});
      const score = adaptiveScoreState.currentScores.get(h3Index) || 0;
      const fillColor = getAdaptiveFillColor(score, adaptiveScoreState.currentMax);
      const highlighted = score >= adaptiveScoreState.threshold;
      const scoreScale = adaptiveScoreState.currentMax > 0
        ? scoreToDisplayValue(score) / Math.max(scoreToDisplayValue(adaptiveScoreState.currentMax), 1e-9)
        : 0;
      return {
        color: highlighted ? '#111827' : '#92400e',
        weight: highlighted ? 2.75 : 1.5,
        opacity: highlighted ? 0.95 : 0.88,
        fillColor,
        fillOpacity: highlighted ? 0.92 : Math.min(0.9, 0.45 + scoreScale * 0.35),
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const h3Index = getAdaptiveH3(p);
      const rawScore = adaptiveScoreState.rawScores.get(h3Index) || 0;
      const currentScore = adaptiveScoreState.currentScores.get(h3Index) || 0;
      const currentMode = adaptiveScoreState.mode === 'raw' ? 'Raw' : 'Smoothed';
      const isHighlighted = currentScore >= adaptiveScoreState.threshold;
      const tooltipLines = [
        'Layer: facility_density_adaptive',
        `Leaf facility count: ${getAdaptiveLeafCount(p).toLocaleString()}`,
        `Cell area: ${formatScoreValue(adaptiveScoreModel.rawAreas.get(h3Index) || 0)} km2`,
        `Resolution: r${getAdaptiveResolution(p)}`,
        `Raw score: ${formatScoreValue(rawScore)}`,
        `Current score (${currentMode.toLowerCase()}): ${formatScoreValue(currentScore)}`,
        `Threshold highlight: ${isHighlighted ? 'yes' : 'no'}`,
        `H3: ${h3Index}`,
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
  const adaptiveScoreModeRaw = document.getElementById('score-mode-raw');
  const adaptiveScoreModeSmoothed = document.getElementById('score-mode-smoothed');
  const adaptiveScoreLambda = document.getElementById('score-lambda');
  const adaptiveScoreIterations = document.getElementById('score-iterations');
  const adaptiveScoreThreshold = document.getElementById('score-threshold');

  function renderAdaptiveCells() {
    const view = computeAdaptiveViewScores();
    adaptiveScoreState.currentScores = view.currentScores;
    adaptiveScoreState.rawScores = view.rawScores || adaptiveScoreState.rawScores;
    adaptiveScoreState.smoothedScores = view.smoothedScores || new Map();
    adaptiveScoreState.currentMin = view.currentMin;
    adaptiveScoreState.currentMax = view.currentMax;
    adaptiveScoreState.scoreMaxForDisplay = view.currentMax;

    if (!adaptiveThresholdInitialized && view.currentMax > 0) {
      adaptiveScoreState.threshold = view.currentMax * 0.5;
      adaptiveThresholdInitialized = true;
    } else if (adaptiveScoreState.threshold > view.currentMax) {
      adaptiveScoreState.threshold = view.currentMax;
    }

    updateAdaptiveScoreControls({ min: view.currentMin, max: view.currentMax });
    clearLayer(adaptiveLayer);
    if (!adaptiveToggle || !adaptiveToggle.checked) return;
    adaptiveLayer.addData(effectiveAdaptiveFeatures);
  }

  let adaptiveRenderQueued = false;
  function scheduleAdaptiveRender() {
    if (adaptiveRenderQueued) return;
    adaptiveRenderQueued = true;
    window.requestAnimationFrame(() => {
      adaptiveRenderQueued = false;
      renderAdaptiveCells();
    });
  }

  if (adaptiveScoreModeRaw) {
    adaptiveScoreModeRaw.addEventListener('change', () => {
      if (!adaptiveScoreModeRaw.checked) return;
      adaptiveScoreState.mode = 'raw';
      scheduleAdaptiveRender();
    });
  }
  if (adaptiveScoreModeSmoothed) {
    adaptiveScoreModeSmoothed.addEventListener('change', () => {
      if (!adaptiveScoreModeSmoothed.checked) return;
      adaptiveScoreState.mode = 'smoothed';
      scheduleAdaptiveRender();
    });
  }
  if (adaptiveScoreLambda) {
    adaptiveScoreLambda.addEventListener('input', () => {
      adaptiveScoreState.lambda = clampNumber(Number(adaptiveScoreLambda.value), 0, 1);
      scheduleAdaptiveRender();
    });
  }
  if (adaptiveScoreIterations) {
    adaptiveScoreIterations.addEventListener('input', () => {
      adaptiveScoreState.iterations = clampNumber(Number(adaptiveScoreIterations.value), 1, 3);
      scheduleAdaptiveRender();
    });
  }
  if (adaptiveScoreThreshold) {
    adaptiveScoreThreshold.addEventListener('input', () => {
      adaptiveScoreState.threshold = buildAdaptiveThresholdFromControl(adaptiveScoreThreshold.value);
      scheduleAdaptiveRender();
    });
  }

  renderAdaptiveCells();

  const r7RegionLayer = L.geoJSON(null, {
    style: (feature) => {
      const p = feature?.properties || {};
      const count = toNumeric(p.layer_value);
      const color = getRegionClusterColor(getRegionClusterId(p));
      return {
        color,
        weight: 1.25,
        fillColor: color,
        fillOpacity: Math.min(0.38, 0.1 + Math.log10(Math.max(1, count + 1)) * 0.08),
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const tooltipLines = [
        'Layer: facility_density_r7_regions',
        `Cluster: ${getRegionClusterId(p) || '--'}`,
        `Cluster size: ${toNumeric(p.cluster_cell_count).toLocaleString()} cells`,
        `Leaf facility count proxy: ${toNumeric(p.layer_value).toLocaleString()}`,
        `Region H3: ${p.region_h3 || '--'}`,
        `Region coordinates: ${toNumeric(p.region_lat).toFixed(6)}, ${toNumeric(p.region_lon).toFixed(6)}`,
        `Resolution: ${formatResolutionTag(p.resolution)}`,
        `H3: ${p.h3 || ''}`,
      ];
      layer.bindTooltip(tooltipLines.join('<br/>'));
    },
  }).addTo(map);
  const r7RegionMarkerLayer = L.geoJSON(null, {
    pointToLayer: (feature, latlng) => {
      const color = getRegionClusterColor(getRegionClusterId(feature?.properties || {}));
      return L.circleMarker(latlng, {
        radius: 5,
        color,
        weight: 2,
        fillColor: color,
        fillOpacity: 0.95,
      });
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const tooltipLines = [
        'Layer: facility_density_r7_regions (region point)',
        `Cluster: ${getRegionClusterId(p) || '--'}`,
        `Cluster size: ${toNumeric(p.cluster_cell_count).toLocaleString()} cells`,
        `Region H3: ${p.region_h3 || '--'}`,
        `Region coordinates: ${toNumeric(p.region_lat).toFixed(6)}, ${toNumeric(p.region_lon).toFixed(6)}`,
      ];
      layer.bindTooltip(tooltipLines.join('<br/>'));
    },
  }).addTo(map);
  const r7RegionsToggle = document.getElementById('toggle-r7-regions');
  const r7RoutesToggle = document.getElementById('toggle-r7-routes');
  function renderR7Regions() {
    clearLayer(r7RegionLayer);
    clearLayer(r7RegionMarkerLayer);
    if (!r7RegionsToggle || !r7RegionsToggle.checked) return;
    r7RegionLayer.addData(r7RegionFeatures);
    r7RegionMarkerLayer.addData(r7RegionMarkerFeatures);
  }
  renderR7Regions();

  const r7RouteLayer = L.geoJSON(null, {
    style: (feature) => {
      const countryCode = feature?.properties?.country_code;
      return {
        color: getR7RouteColor(countryCode),
        weight: 1.5,
        opacity: 0.2,
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature?.properties || {};
      const tooltipLines = [
        'Layer: r7_region_routes',
        `Country: ${p.country_code || '--'}`,
        `From: ${p.from_region_h3 || '--'}`,
        `To: ${p.to_region_h3 || '--'}`,
        `Distance: ${formatDistanceKm(p.distance_m)}`,
        `Duration: ${formatDurationMinutes(p.duration_s)}`,
      ];
      layer.bindTooltip(tooltipLines.join('<br/>'));
    },
  }).addTo(map);

  async function loadR7RouteOverlay() {
    if (r7RouteOverlay) return r7RouteOverlay;
    if (!r7RouteOverlayPromise) {
      r7RouteOverlayPromise = dataSource.loadR7RouteOverlay();
    }
    r7RouteOverlay = await r7RouteOverlayPromise;
    return r7RouteOverlay;
  }

  async function renderR7Routes() {
    clearLayer(r7RouteLayer);
    if (!r7RoutesToggle || !r7RoutesToggle.checked) return;
    const routeOverlay = await loadR7RouteOverlay();
    if (!r7RoutesToggle.checked || !routeOverlay) return;
    r7RouteLayer.addData(routeOverlay);
  }
  await renderR7Routes();

  const combined = L.featureGroup([facilityLayer, countryLayer, adaptiveLayer, r7RegionLayer, r7RegionMarkerLayer]);
  if (combined.getBounds().isValid()) {
    map.fitBounds(combined.getBounds(), { padding: [20, 20] });
  }

  if (facilityToggle) {
    facilityToggle.addEventListener('change', () => {
      renderFacilities();
    });
  }
  if (countryToggle) {
    countryToggle.addEventListener('change', () => {
      renderCountryCells();
    });
  }
  if (adaptiveToggle) {
    adaptiveToggle.addEventListener('change', () => {
      scheduleAdaptiveRender();
    });
  }
  if (r7RegionsToggle) {
    r7RegionsToggle.addEventListener('change', () => {
      renderR7Regions();
    });
  }
  if (r7RoutesToggle) {
    r7RoutesToggle.addEventListener('change', () => {
      renderR7Routes();
    });
  }
}

init().catch((error) => {
  const node = document.getElementById('drilldown-content');
  node.textContent = `UI load error: ${error.message}`;
});
