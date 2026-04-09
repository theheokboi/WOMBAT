(function attachInframapShared(globalObject) {
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

  function getRequestedDataMode() {
    const params = new URLSearchParams(window.location.search);
    const value = String(params.get('data') || '').trim().toLowerCase();
    return value === 'static' || value === 'api' ? value : '';
  }

  async function detectDataSource() {
    const requestedMode = getRequestedDataMode();
    const staticManifest = requestedMode === 'api' ? null : await tryLoadJson('demo-data/manifest.json');
    if (requestedMode === 'static') {
      if (!staticManifest) throw new Error('Static demo data requested but demo-data/manifest.json is unavailable');
      return { mode: 'static', staticManifest, liveUiConfig: null };
    }
    const liveUiConfig = await tryLoadJson('/v1/ui/config');
    if (liveUiConfig) {
      return { mode: 'api', staticManifest, liveUiConfig };
    }
    if (staticManifest) {
      return { mode: 'static', staticManifest, liveUiConfig: null };
    }
    throw new Error('Unable to load live API or static demo data');
  }

  function featureCollectionFeatures(collection) {
    return Array.isArray(collection?.features) ? collection.features : [];
  }

  function normalizeRunId(value) {
    if (value === null || value === undefined) return '';
    return String(value).trim();
  }

  globalObject.inframapShared = {
    detectDataSource,
    featureCollectionFeatures,
    loadJson,
    normalizeRunId,
    tryLoadJson,
  };
}(window));
