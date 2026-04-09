const {
  detectDataSource,
  featureCollectionFeatures,
  loadJson,
  normalizeRunId,
  tryLoadJson,
} = window.inframapShared;

function createDataSource({ mode, staticManifest, liveUiConfig }) {
  if (mode === 'static') {
    return {
      mode,
      staticManifest,
      loadUiConfig: async () => loadJson('demo-data/ui-config.json'),
      loadRunsCatalog: async () => loadJson('demo-data/runs-catalog.json'),
      loadFacilities: async () => loadJson('demo-data/facilities.json'),
      loadActiveStatus: async () => tryLoadJson('demo-data/active-status.json'),
    };
  }
  return {
    mode,
    staticManifest,
    loadUiConfig: async () => liveUiConfig || loadJson('/v1/ui/config'),
    loadRunsCatalog: async () => tryLoadJson('/v1/runs/catalog'),
    loadFacilities: async (runId) => {
      const url = new URL('/v1/facilities?limit=50000', window.location.origin);
      if (runId) url.searchParams.set('run_id', runId);
      return loadJson(`${url.pathname}?${url.searchParams.toString()}`);
    },
    loadActiveStatus: async () => tryLoadJson('/v1/runs/active/status'),
  };
}

function getRequestedRunId() {
  const params = new URLSearchParams(window.location.search);
  return normalizeRunId(params.get('run'));
}

function clampInteger(value, min, max, fallback) {
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function getRequestedKRingParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    resolution: clampInteger(params.get('resolution'), 5, 8, 7),
    datacenterK: clampInteger(params.get('datacenter_k'), 0, 4, 2),
    landingK: clampInteger(params.get('landing_k'), 0, 4, 1),
  };
}

function formatResolution(resolution) {
  return `r${resolution}`;
}

function formatCount(value) {
  return Number(value || 0).toLocaleString();
}

function syncKRingUrl({ runId, params }) {
  const nextUrl = new URL(window.location.href);
  if (runId) {
    nextUrl.searchParams.set('run', runId);
  } else {
    nextUrl.searchParams.delete('run');
  }
  nextUrl.searchParams.set('resolution', String(params.resolution));
  nextUrl.searchParams.set('datacenter_k', String(params.datacenterK));
  nextUrl.searchParams.set('landing_k', String(params.landingK));
  window.history.replaceState({}, '', `${nextUrl.pathname}${nextUrl.search}`);
}

function buildRunLabel(run) {
  const runId = normalizeRunId(run?.run_id) || '--';
  const mode = run?.country_mask_mode ? String(run.country_mask_mode) : '--';
  const resolution = Number.isInteger(Number(run?.country_mask_resolution))
    ? `r${Number(run.country_mask_resolution)}`
    : '--';
  return `${resolution} | ${mode} | ${runId}`;
}

function setupRunSelector(runCatalog, requestedRunId, effectiveRunId, onRunChange) {
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
  selector.value = effectiveRunId;
  selector.disabled = runs.length === 0;
  selector.title = `Requested: ${requestedRunId || '--'}; Effective: ${effectiveRunId || '--'}`;
  selector.addEventListener('change', () => {
    void onRunChange(normalizeRunId(selector.value)).catch((error) => {
      const node = document.getElementById('drilldown-content');
      if (node) node.textContent = `Run load error: ${error.message}`;
    });
  });
}

function clearLayer(layer) {
  if (layer) layer.clearLayers();
}

function isLandingPointFeature(feature) {
  const source = String(feature?.properties?.source_name || '').toLowerCase();
  return source.includes('landing');
}

function hashString(value) {
  const text = String(value || '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function getFeatureCoordinates(feature) {
  const coordinates = feature?.geometry?.coordinates;
  if (!Array.isArray(coordinates) || coordinates.length < 2) return null;
  const [lon, lat] = coordinates;
  if (!Number.isFinite(Number(lat)) || !Number.isFinite(Number(lon))) return null;
  return { lat: Number(lat), lon: Number(lon) };
}

const FACILITY_POINT_COLOR = '#f97316';
const LANDING_POINT_COLOR = '#0ea5e9';
const REGION_COLORS = ['#0f766e', '#1d4ed8', '#7c3aed', '#b45309', '#be123c', '#4338ca'];
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

function getRegionColor(regionId) {
  return REGION_COLORS[hashString(regionId) % REGION_COLORS.length];
}

function buildKRingRegions(facilityFeatures, params) {
  const resolution = clampInteger(params?.resolution, 5, 8, 7);
  const datacenterK = clampInteger(params?.datacenterK, 0, 4, 2);
  const landingK = clampInteger(params?.landingK, 0, 4, 1);
  const seedRecords = [];
  const allCells = new Set();

  for (const feature of facilityFeatures) {
    const coordinates = getFeatureCoordinates(feature);
    if (!coordinates) continue;
    const seedCell = h3.latLngToCell(coordinates.lat, coordinates.lon, resolution);
    const landing = isLandingPointFeature(feature);
    const k = landing ? landingK : datacenterK;
    const ringCells = h3.gridDisk(seedCell, k);
    for (const cell of ringCells) allCells.add(cell);
    seedRecords.push({
      feature,
      facilityId: String(feature?.properties?.facility_id || `${seedCell}:${seedRecords.length}`),
      landing,
      k,
      seedCell,
      coverageCellCount: ringCells.length,
    });
  }

  const sortedCells = Array.from(allCells).sort();
  const regions = [];
  const regionByCell = new Map();
  const remaining = new Set(sortedCells);

  while (remaining.size > 0) {
    const startCell = remaining.values().next().value;
    remaining.delete(startCell);
    const queue = [startCell];
    const cells = [];

    while (queue.length > 0) {
      const cell = queue.shift();
      cells.push(cell);
      const neighbors = h3.gridDisk(cell, 1);
      for (const neighbor of neighbors) {
        if (neighbor === cell || !remaining.has(neighbor)) continue;
        remaining.delete(neighbor);
        queue.push(neighbor);
      }
    }

    cells.sort();
    regions.push({
      regionId: `region-${cells[0]}`,
      sortKey: cells[0],
      cells,
      landingSeedCount: 0,
      datacenterSeedCount: 0,
      totalSeedCount: 0,
      representativeCell: cells[0],
      representativeLat: 0,
      representativeLon: 0,
    });
  }

  regions.sort((left, right) => left.sortKey.localeCompare(right.sortKey));

  for (const region of regions) {
    for (const cell of region.cells) {
      regionByCell.set(cell, region.regionId);
    }
  }

  const regionIndex = new Map(regions.map((region) => [region.regionId, region]));
  for (const seed of seedRecords) {
    const regionId = regionByCell.get(seed.seedCell);
    if (!regionId) continue;
    const region = regionIndex.get(regionId);
    if (!region) continue;
    region.totalSeedCount += 1;
    if (seed.landing) {
      region.landingSeedCount += 1;
    } else {
      region.datacenterSeedCount += 1;
    }
  }

  for (const region of regions) {
    let latSum = 0;
    let lonSum = 0;
    for (const cell of region.cells) {
      const [lat, lon] = h3.cellToLatLng(cell);
      latSum += lat;
      lonSum += lon;
    }
    region.representativeLat = region.cells.length > 0 ? latSum / region.cells.length : 0;
    region.representativeLon = region.cells.length > 0 ? lonSum / region.cells.length : 0;
    region.representativeCell = region.cells.reduce((bestCell, candidateCell) => {
      const [candidateLat, candidateLon] = h3.cellToLatLng(candidateCell);
      const [bestLat, bestLon] = h3.cellToLatLng(bestCell);
      const candidateDistance =
        ((candidateLat - region.representativeLat) ** 2) + ((candidateLon - region.representativeLon) ** 2);
      const bestDistance =
        ((bestLat - region.representativeLat) ** 2) + ((bestLon - region.representativeLon) ** 2);
      return candidateDistance < bestDistance ? candidateCell : bestCell;
    }, region.cells[0]);
  }

  const regionFeatures = [];
  for (const region of regions) {
    const color = getRegionColor(region.regionId);
    for (const cell of region.cells) {
      const boundary = h3.cellToBoundary(cell);
      const ring = boundary.map(([lat, lon]) => [lon, lat]);
      if (ring.length > 0) {
        const first = ring[0];
        const last = ring[ring.length - 1];
        if (first[0] !== last[0] || first[1] !== last[1]) ring.push([first[0], first[1]]);
      }
      regionFeatures.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [ring],
        },
        properties: {
          region_id: region.regionId,
          region_color: color,
          cell_count: region.cells.length,
          landing_seed_count: region.landingSeedCount,
          datacenter_seed_count: region.datacenterSeedCount,
          total_seed_count: region.totalSeedCount,
          representative_h3: region.representativeCell,
          representative_lat: region.representativeLat,
          representative_lon: region.representativeLon,
          h3: cell,
          resolution,
          datacenter_k: datacenterK,
          landing_k: landingK,
        },
      });
    }
  }

  return {
    params: { resolution, datacenterK, landingK },
    regionFeatures,
    regions,
    seedRecords,
    seedCellCount: new Set(seedRecords.map((record) => record.seedCell)).size,
    totalExpandedCells: allCells.size,
    facilityCount: seedRecords.filter((record) => !record.landing).length,
    landingCount: seedRecords.filter((record) => record.landing).length,
  };
}

function formatActiveRunStatus(activeStatus) {
  if (activeStatus?.active) {
    const stage = activeStatus?.active_status?.stage || '--';
    const elapsed = activeStatus?.active_status?.elapsed_s;
    const elapsedLabel = typeof elapsed === 'number' ? `${elapsed.toFixed(1)}s` : '--';
    return `Active run: in progress (${stage}, elapsed ${elapsedLabel})`;
  }
  return 'Active run: none';
}

async function init() {
  const detectedDataSource = await detectDataSource();
  const dataSource = createDataSource(detectedDataSource);
  const [ui, runCatalog] = await Promise.all([
    dataSource.loadUiConfig(),
    dataSource.loadRunsCatalog(),
  ]);

  const requestedRunId = getRequestedRunId();
  const requestedParams = getRequestedKRingParams();
  const runs = Array.isArray(runCatalog?.runs) ? runCatalog.runs : [];
  const runIdSet = new Set(runs.map((run) => normalizeRunId(run?.run_id)).filter(Boolean));
  const latestCatalogRunId = normalizeRunId(runCatalog?.latest_run_id);
  let effectiveRunId = requestedRunId;
  if (!effectiveRunId || !runIdSet.has(effectiveRunId)) {
    effectiveRunId = latestCatalogRunId || (runs[0] ? normalizeRunId(runs[0].run_id) : '');
  }
  setupRunSelector(runCatalog, requestedRunId, effectiveRunId, async (nextRunId) => {
    await loadRunData(nextRunId, { fitBounds: true });
  });

  const [lon, lat] = ui.center;
  const map = L.map('map', {
    center: [lat, lon],
    zoom: ui.zoom,
    preferCanvas: true,
    zoomControl: true,
  });
  window.__inframapKRingMap = map;
  window.__inframapKRingModel = null;

  const basemapSelector = document.getElementById('basemap-selector');
  const resolutionControl = document.getElementById('resolution-control');
  const datacenterKControl = document.getElementById('datacenter-k-control');
  const landingKControl = document.getElementById('landing-k-control');
  const resolutionValue = document.getElementById('resolution-value');
  const datacenterKValue = document.getElementById('datacenter-k-value');
  const landingKValue = document.getElementById('landing-k-value');
  const summaryNode = document.getElementById('k-rings-summary');
  const displayScopeNode = document.getElementById('display-scope');
  const selectedRunNode = document.getElementById('selected-run');
  const selectedSourceNode = document.getElementById('selected-source');
  const activeRunStatusNode = document.getElementById('active-run-status');
  const paramCountNode = document.getElementById('param-count');
  const facilityCountNode = document.getElementById('facility-count');
  const landingCountNode = document.getElementById('landing-count');
  const seedCountNode = document.getElementById('seed-count');
  const ringCellCountNode = document.getElementById('ring-cell-count');
  const regionCountNode = document.getElementById('region-count');
  const drilldownNode = document.getElementById('drilldown-content');

  const createBasemapLayer = (basemapId) => {
    const id = BASEMAP_STYLES[basemapId] ? basemapId : 'positron';
    const style = BASEMAP_STYLES[id];
    return L.tileLayer(style.url, style.options);
  };
  let currentBasemap = 'positron';
  let basemapLayer = createBasemapLayer(currentBasemap).addTo(map);
  basemapSelector?.addEventListener('change', () => {
    const nextBasemap = BASEMAP_STYLES[basemapSelector.value] ? basemapSelector.value : 'positron';
    if (nextBasemap === currentBasemap) return;
    if (basemapLayer) map.removeLayer(basemapLayer);
    basemapLayer = createBasemapLayer(nextBasemap).addTo(map);
    currentBasemap = nextBasemap;
  });

  const appState = {
    runId: effectiveRunId,
    params: requestedParams,
    facilities: null,
    activeStatus: null,
    facilityFeatures: [],
    model: null,
    shouldFitBounds: true,
  };

  function renderSummary(model) {
    if (!summaryNode) return;
    summaryNode.innerHTML = '';

    const rows = [
      ['Run', appState.runId || '--'],
      ['Source', dataSource.mode],
      ['Resolution', formatResolution(model.params.resolution)],
      ['Datacenter k', String(model.params.datacenterK)],
      ['Landing-point k', String(model.params.landingK)],
      ['Seed cells', formatCount(model.seedCellCount)],
      ['Expanded cells', formatCount(model.totalExpandedCells)],
      ['Regions', formatCount(model.regions.length)],
    ];

    for (const [label, value] of rows) {
      const row = document.createElement('div');
      row.className = 'summary-row';
      const labelNode = document.createElement('span');
      labelNode.textContent = `${label}:`;
      const valueNode = document.createElement('strong');
      valueNode.textContent = value;
      row.append(labelNode, valueNode);
      summaryNode.appendChild(row);
    }
  }

  function updateParamControls(params) {
    if (resolutionControl) resolutionControl.value = String(params.resolution);
    if (datacenterKControl) datacenterKControl.value = String(params.datacenterK);
    if (landingKControl) landingKControl.value = String(params.landingK);
    if (resolutionValue) resolutionValue.textContent = formatResolution(params.resolution);
    if (datacenterKValue) datacenterKValue.textContent = String(params.datacenterK);
    if (landingKValue) landingKValue.textContent = String(params.landingK);
  }

  function renderStatus() {
    const featureCount = appState.facilityFeatures.length;
    const landingCount = appState.model?.landingCount || 0;
    const currentParams = appState.model?.params || appState.params;

    if (displayScopeNode) {
      displayScopeNode.textContent =
        `Display scope: run=${appState.runId || '--'}; source=${dataSource.mode}; mode=k-rings; ` +
        `resolution=${formatResolution(currentParams.resolution)}; ` +
        `datacenter k=${currentParams.datacenterK}; landing-point k=${currentParams.landingK}; ` +
        `${featureCount.toLocaleString()} facility points loaded.`;
    }
    if (paramCountNode) {
      paramCountNode.textContent =
        `Current parameters: ${formatResolution(currentParams.resolution)}; ` +
        `datacenter k=${currentParams.datacenterK}; landing-point k=${currentParams.landingK}`;
    }
    if (facilityCountNode) {
      facilityCountNode.textContent =
        `Non-landing facilities: ${formatCount(appState.model?.facilityCount || 0)}`;
    }
    if (landingCountNode) {
      landingCountNode.textContent = `Landing points: ${formatCount(landingCount)}`;
    }
    if (seedCountNode) {
      seedCountNode.textContent =
        `Seed cells (${formatResolution(currentParams.resolution)}): ${formatCount(appState.model?.seedCellCount || 0)}`;
    }
    if (ringCellCountNode) {
      ringCellCountNode.textContent =
        `Expanded cells: ${formatCount(appState.model?.totalExpandedCells || 0)}`;
    }
    if (regionCountNode) {
      regionCountNode.textContent =
        `Contiguous regions: ${formatCount(appState.model?.regions.length || 0)}`;
    }
    if (selectedRunNode) selectedRunNode.textContent = `Selected run: ${appState.runId || '--'}`;
    if (selectedSourceNode) selectedSourceNode.textContent = `Data source: ${dataSource.mode}`;
    if (activeRunStatusNode) activeRunStatusNode.textContent = formatActiveRunStatus(appState.activeStatus);
  }

  function updateDrilldown(message) {
    if (drilldownNode) drilldownNode.textContent = message;
  }

  function renderFacilitiesLayer() {
    clearLayer(facilitiesLayer);
    if (!facilityToggle?.checked) return;
    facilitiesLayer.addData({
      type: 'FeatureCollection',
      features: appState.facilityFeatures,
    });
  }

  function renderRegionsLayer() {
    clearLayer(regionLayer);
    if (!kRingToggle?.checked || !appState.model) return;
    regionLayer.addData({
      type: 'FeatureCollection',
      features: appState.model.regionFeatures,
    });
  }

  function renderLayers() {
    renderFacilitiesLayer();
    renderRegionsLayer();
    if (!appState.shouldFitBounds) return;
    const visibleLayers = [];
    if (facilityToggle?.checked) visibleLayers.push(facilitiesLayer);
    if (kRingToggle?.checked) visibleLayers.push(regionLayer);
    const combined = L.featureGroup(visibleLayers);
    if (combined.getBounds().isValid()) {
      map.fitBounds(combined.getBounds(), { padding: [20, 20] });
      appState.shouldFitBounds = false;
    }
  }

  let loadSequence = 0;
  function recomputeKRingModel() {
    if (!appState.facilityFeatures.length) {
      appState.model = {
        params: appState.params,
        regionFeatures: [],
        regions: [],
        seedRecords: [],
        seedCellCount: 0,
        totalExpandedCells: 0,
        facilityCount: 0,
        landingCount: 0,
      };
      window.__inframapKRings = appState.model;
      window.__inframapKRingModel = appState.model;
      renderSummary(appState.model);
      renderStatus();
      renderLayers();
      return;
    }
    const model = buildKRingRegions(appState.facilityFeatures, appState.params);
    appState.model = model;
    window.__inframapKRings = model;
    window.__inframapKRingModel = model;
    renderSummary(model);
    renderStatus();
    renderLayers();
  }

  let recomputeTimer = null;
  function scheduleRecompute() {
    if (recomputeTimer) window.clearTimeout(recomputeTimer);
    recomputeTimer = window.setTimeout(() => {
      recomputeTimer = null;
      syncKRingUrl({ runId: appState.runId, params: appState.params });
      recomputeKRingModel();
    }, 120);
  }

  function updateParams(nextParams, { recompute = true } = {}) {
    appState.params = {
      resolution: clampInteger(nextParams.resolution, 5, 8, appState.params.resolution),
      datacenterK: clampInteger(nextParams.datacenterK, 0, 4, appState.params.datacenterK),
      landingK: clampInteger(nextParams.landingK, 0, 4, appState.params.landingK),
    };
    updateParamControls(appState.params);
    syncKRingUrl({ runId: appState.runId, params: appState.params });
    if (recompute) scheduleRecompute();
  }

  async function loadRunData(nextRunId, { fitBounds = false } = {}) {
    const requestId = loadSequence + 1;
    loadSequence = requestId;
    appState.runId = nextRunId;
    appState.shouldFitBounds = fitBounds;
    appState.facilities = null;
    appState.facilityFeatures = [];
    appState.model = null;
    if (summaryNode) summaryNode.innerHTML = '';
    syncKRingUrl({ runId: appState.runId, params: appState.params });
    renderStatus();
    renderLayers();
    updateDrilldown(
      `Hover a region or point to inspect the parameterized k-disk groups at ${formatResolution(appState.params.resolution)}.`
    );
    const facilities = await dataSource.loadFacilities(nextRunId);
    if (requestId !== loadSequence) return;
    appState.facilities = facilities;
    appState.facilityFeatures = featureCollectionFeatures(facilities);
    renderStatus();
    recomputeKRingModel();
  }

  appState.activeStatus = await dataSource.loadActiveStatus();
  updateParamControls(appState.params);
  setupRunSelector(runCatalog, requestedRunId, effectiveRunId, async (nextRunId) => {
    if (!nextRunId || nextRunId === appState.runId) return;
    await loadRunData(nextRunId, { fitBounds: true });
  });

  const facilitiesLayer = L.geoJSON(null, {
    pointToLayer: (feature, latlng) => {
      const landing = isLandingPointFeature(feature);
      return L.circleMarker(latlng, {
        radius: landing ? 4 : 5,
        color: '#ffffff',
        weight: 1,
        fillColor: landing ? LANDING_POINT_COLOR : FACILITY_POINT_COLOR,
        fillOpacity: 0.95,
      });
    },
    onEachFeature: (feature, layer) => {
      const coordinates = getFeatureCoordinates(feature);
      const seedCell = coordinates
        ? h3.latLngToCell(coordinates.lat, coordinates.lon, appState.params.resolution)
        : '--';
      const landing = isLandingPointFeature(feature);
      layer.bindTooltip(
        `Type: ${landing ? 'Landing point' : 'Facility'}<br/>` +
        `Source: ${feature?.properties?.source_name || ''}<br/>` +
        `Org: ${feature?.properties?.org_name || ''}<br/>` +
        `Seed ${formatResolution(appState.params.resolution)}: ${seedCell}<br/>` +
        `K value: ${landing ? appState.params.landingK : appState.params.datacenterK}`
      );
      layer.on('mouseover', () => {
        updateDrilldown(
          `${landing ? 'Landing point' : 'Facility'} ${feature?.properties?.facility_id || '--'} seeds ` +
          `cell ${seedCell} at ${formatResolution(appState.params.resolution)} and expands with ` +
          `gridDisk(seed, ${landing ? appState.params.landingK : appState.params.datacenterK}).`
        );
      });
      layer.on('mouseout', () => {
        updateDrilldown(
          `Hover a region or point to inspect the parameterized k-disk groups at ${formatResolution(appState.params.resolution)}.`
        );
      });
    },
  }).addTo(map);

  const regionLayer = L.geoJSON(null, {
    style: (feature) => {
      const color = feature?.properties?.region_color || '#0f766e';
      return {
        color,
        weight: 1.5,
        fillColor: color,
        fillOpacity: 0.32,
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature?.properties || {};
      const resolution = Number.isFinite(Number(p.resolution)) ? Number(p.resolution) : appState.params.resolution;
      const datacenterK = Number.isFinite(Number(p.datacenter_k)) ? Number(p.datacenter_k) : appState.params.datacenterK;
      const landingK = Number.isFinite(Number(p.landing_k)) ? Number(p.landing_k) : appState.params.landingK;
      layer.bindTooltip(
        'Layer: k_rings_regions<br/>' +
        `Region: ${p.region_id || '--'}<br/>` +
        `Resolution: ${formatResolution(resolution)}<br/>` +
        `Datacenter k: ${datacenterK.toLocaleString()}<br/>` +
        `Landing-point k: ${landingK.toLocaleString()}<br/>` +
        `Region cells: ${Number(p.cell_count || 0).toLocaleString()}<br/>` +
        `Facility seeds: ${Number(p.datacenter_seed_count || 0).toLocaleString()}<br/>` +
        `Landing seeds: ${Number(p.landing_seed_count || 0).toLocaleString()}<br/>` +
        `Total seeds: ${Number(p.total_seed_count || 0).toLocaleString()}<br/>` +
        `Representative H3: ${p.representative_h3 || '--'}<br/>` +
        `Cell H3: ${p.h3 || '--'}`
      );
      layer.on('mouseover', () => {
        updateDrilldown(
          `Region ${p.region_id || '--'} contains ${Number(p.cell_count || 0).toLocaleString()} cells and ` +
          `${Number(p.total_seed_count || 0).toLocaleString()} total seed points at ` +
          `${formatResolution(resolution)} with ` +
          `datacenter k=${datacenterK} and landing-point k=${landingK}.`
        );
      });
    },
  }).addTo(map);

  const facilityToggle = document.getElementById('toggle-facilities');
  const kRingToggle = document.getElementById('toggle-k-rings');
  facilityToggle?.addEventListener('change', renderLayers);
  kRingToggle?.addEventListener('change', renderLayers);
  resolutionControl?.addEventListener('input', () => {
    updateParams({
      ...appState.params,
      resolution: resolutionControl.value,
    });
  });
  datacenterKControl?.addEventListener('input', () => {
    updateParams({
      ...appState.params,
      datacenterK: datacenterKControl.value,
    });
  });
  landingKControl?.addEventListener('input', () => {
    updateParams({
      ...appState.params,
      landingK: landingKControl.value,
    });
  });

  await loadRunData(effectiveRunId, { fitBounds: true });
  updateParamControls(appState.params);
  renderStatus();
  renderLayers();
  window.__inframapMap = map;
}

init().catch((error) => {
  const node = document.getElementById('drilldown-content');
  node.textContent = `UI load error: ${error.message}`;
});
