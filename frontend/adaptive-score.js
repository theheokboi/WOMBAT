(function attachAdaptiveScore(globalObject) {
  function clampNumber(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function formatScoreValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '--';
    if (numeric === 0) return '0';
    if (Math.abs(numeric) >= 10000 || Math.abs(numeric) < 0.001) {
      return numeric.toExponential(2);
    }
    return numeric.toFixed(3);
  }

  function scoreToDisplayValue(score) {
    return Math.log1p(Math.max(0, Number(score) || 0));
  }

  function displayValueToScore(value) {
    return Math.expm1(Math.max(0, Number(value) || 0));
  }

  function hexToRgb(hex) {
    const normalized = String(hex || '').replace('#', '');
    if (normalized.length !== 6) return null;
    const parsed = Number.parseInt(normalized, 16);
    if (!Number.isFinite(parsed)) return null;
    return {
      r: (parsed >> 16) & 255,
      g: (parsed >> 8) & 255,
      b: parsed & 255,
    };
  }

  function rgbToHex({ r, g, b }) {
    const clampChannel = (channel) => clampNumber(Math.round(channel), 0, 255);
    return `#${[clampChannel(r), clampChannel(g), clampChannel(b)].map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;
  }

  function interpolateColor(start, end, t) {
    const from = hexToRgb(start);
    const to = hexToRgb(end);
    if (!from || !to) return start;
    const clampedT = clampNumber(t, 0, 1);
    return rgbToHex({
      r: from.r + (to.r - from.r) * clampedT,
      g: from.g + (to.g - from.g) * clampedT,
      b: from.b + (to.b - from.b) * clampedT,
    });
  }

  function interpolateColorStops(stops, t) {
    if (!Array.isArray(stops) || stops.length === 0) return '#d97706';
    if (stops.length === 1) return stops[0];
    const clampedT = clampNumber(t, 0, 1);
    const scaled = clampedT * (stops.length - 1);
    const startIndex = Math.floor(scaled);
    const endIndex = Math.min(stops.length - 1, startIndex + 1);
    const localT = scaled - startIndex;
    return interpolateColor(stops[startIndex], stops[endIndex], localT);
  }

  function getAdaptiveScoreMass(properties) {
    return getAdaptiveLeafCount(properties);
  }

  function buildAdaptiveAnalysisResolution(adaptiveFeatures, adaptiveMetadata) {
    const observedMax = (adaptiveFeatures || []).reduce((max, feature) => Math.max(max, getAdaptiveResolution(feature?.properties || {})), 0);
    const configured = parseIntegerOrDefault(adaptiveMetadata?.params?.facility_floor_resolution, observedMax || 6);
    const candidate = Number.isInteger(configured) ? configured : (observedMax || 6);
    const maxAnalysisResolution = Math.min(6, Math.max(0, observedMax || 6));
    return clampNumber(candidate || maxAnalysisResolution || 6, 0, maxAnalysisResolution || 6);
  }

  function buildAdaptiveScoreModel(adaptiveFeatures, adaptiveMetadata) {
    const analysisResolution = buildAdaptiveAnalysisResolution(adaptiveFeatures, adaptiveMetadata);
    const originals = [];
    const analysisMasses = new Map();
    const analysisSources = new Map();
    const rawAreas = new Map();
    const rawScores = new Map();

    for (const feature of adaptiveFeatures || []) {
      const properties = feature?.properties || {};
      const h3Index = getAdaptiveH3(properties);
      const resolution = getAdaptiveResolution(properties);
      if (!h3Index || !Number.isInteger(Number(resolution))) continue;

      const mass = getAdaptiveScoreMass(properties);
      const areaKm2 = h3.cellArea(h3Index, h3.UNITS?.km2 || 'km2');
      const rawScore = areaKm2 > 0 ? mass / areaKm2 : 0;
      originals.push({ h3: h3Index, areaKm2, rawScore });
      rawAreas.set(h3Index, areaKm2);
      rawScores.set(h3Index, rawScore);

      if (resolution < analysisResolution) {
        const analysisCells = h3.cellToChildren(h3Index, analysisResolution);
        const childCount = analysisCells.length || 1;
        const childMass = childCount > 0 ? mass / childCount : mass;
        for (const child of analysisCells) {
          analysisMasses.set(child, (analysisMasses.get(child) || 0) + childMass);
          const sources = analysisSources.get(child) || [];
          sources.push({ originalH3: h3Index, contributionMass: childMass });
          analysisSources.set(child, sources);
        }
        continue;
      }

      const analysisCell = resolution === analysisResolution ? h3Index : h3.cellToParent(h3Index, analysisResolution);
      analysisMasses.set(analysisCell, (analysisMasses.get(analysisCell) || 0) + mass);
      const sources = analysisSources.get(analysisCell) || [];
      sources.push({ originalH3: h3Index, contributionMass: mass });
      analysisSources.set(analysisCell, sources);
    }

    const analysisCells = Array.from(analysisMasses.keys()).sort();
    const analysisCellIndex = new Map(analysisCells.map((cell, index) => [cell, index]));
    const analysisNeighbors = analysisCells.map((cell) => {
      const neighbors = [];
      for (const neighbor of h3.gridDisk(cell, 1)) {
        if (neighbor === cell) continue;
        const neighborIndex = analysisCellIndex.get(neighbor);
        if (neighborIndex !== undefined) neighbors.push(neighborIndex);
      }
      return neighbors;
    });

    return {
      analysisCells,
      analysisMasses,
      analysisNeighbors,
      analysisResolution,
      analysisSources,
      originals,
      rawAreas,
      rawScores,
    };
  }

  function smoothAnalysisMasses(baseMasses, neighborIndices, lambdaValue, iterations) {
    const baseTotal = baseMasses.reduce((sum, value) => sum + value, 0);
    let current = baseMasses.slice();
    const lambda = clampNumber(lambdaValue, 0, 1);
    const iterationCount = clampNumber(Number(iterations) || 1, 1, 3);

    for (let iteration = 0; iteration < iterationCount; iteration += 1) {
      const next = new Array(current.length);
      for (let index = 0; index < current.length; index += 1) {
        const neighbors = neighborIndices[index] || [];
        let neighborSum = 0;
        for (const neighborIndex of neighbors) {
          neighborSum += current[neighborIndex];
        }
        const neighborAverage = neighbors.length > 0 ? neighborSum / neighbors.length : current[index];
        next[index] = ((1 - lambda) * current[index]) + (lambda * neighborAverage);
      }
      const nextTotal = next.reduce((sum, value) => sum + value, 0);
      const scale = nextTotal > 0 ? baseTotal / nextTotal : 1;
      current = next.map((value) => value * scale);
    }

    return current;
  }

  function buildAdaptiveCurrentScores(model, smoothedAnalysisMasses) {
    const smoothedMassByOriginal = new Map();
    const analysisScoresByCell = new Map();

    for (let index = 0; index < model.analysisCells.length; index += 1) {
      const analysisCell = model.analysisCells[index];
      const smoothedMass = smoothedAnalysisMasses[index] || 0;
      analysisScoresByCell.set(analysisCell, smoothedMass);
      const sources = model.analysisSources.get(analysisCell) || [];
      const totalContributionMass = sources.reduce((sum, source) => sum + source.contributionMass, 0);
      if (totalContributionMass <= 0) continue;
      for (const source of sources) {
        const share = source.contributionMass / totalContributionMass;
        const nextMass = (smoothedMassByOriginal.get(source.originalH3) || 0) + (smoothedMass * share);
        smoothedMassByOriginal.set(source.originalH3, nextMass);
      }
    }

    const rawScoresByOriginal = new Map(model.rawScores);
    const smoothedScoresByOriginal = new Map();
    for (const original of model.originals) {
      const mass = smoothedMassByOriginal.get(original.h3) || 0;
      const score = original.areaKm2 > 0 ? mass / original.areaKm2 : 0;
      smoothedScoresByOriginal.set(original.h3, score);
    }

    return {
      analysisScoresByCell,
      rawScoresByOriginal,
      smoothedScoresByOriginal,
    };
  }

  function buildAdaptiveScoreScale(scores) {
    const values = Array.from(scores.values()).filter((value) => Number.isFinite(value));
    const min = values.length > 0 ? Math.min(...values) : 0;
    const max = values.length > 0 ? Math.max(...values) : 0;
    return { min, max };
  }

  function buildAdaptiveThresholdFromControl(controlValue) {
    return displayValueToScore(controlValue);
  }

  function buildAdaptiveControlValueFromThreshold(threshold) {
    return scoreToDisplayValue(threshold);
  }

  globalObject.inframapAdaptiveScore = {
    buildAdaptiveAnalysisResolution,
    buildAdaptiveControlValueFromThreshold,
    buildAdaptiveCurrentScores,
    buildAdaptiveScoreModel,
    buildAdaptiveScoreScale,
    buildAdaptiveThresholdFromControl,
    clampNumber,
    displayValueToScore,
    formatScoreValue,
    interpolateColorStops,
    scoreToDisplayValue,
    smoothAnalysisMasses,
  };
}(window));
