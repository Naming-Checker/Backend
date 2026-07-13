import http from "k6/http";
import { check, sleep } from "k6";

const RAW_QUERIES = open("/data/queries.json");
const QUERY_ITEMS = JSON.parse(RAW_QUERIES);
const LOGO_FILE_PATH = __ENV.K6_LOGO_FILE || "/data/sample-logo.png";
const LOGO_BINARY = open(LOGO_FILE_PATH, "b");

function pickQuery() {
  const idx = (__VU + __ITER) % QUERY_ITEMS.length;
  return QUERY_ITEMS[idx];
}

function parseJson(response) {
  try {
    return response.json();
  } catch (_) {
    return null;
  }
}

function extractPreviewPath(payload) {
  if (!payload) {
    return "";
  }

  const candidates = [];

  if (Array.isArray(payload.matches)) {
    for (const item of payload.matches) {
      if (!item || typeof item !== "object") {
        continue;
      }
      candidates.push(item.logo_path, item.preview_path, item.path, item.logoPath, item.previewPath);
    }
  }

  candidates.push(payload.logo_path, payload.preview_path, payload.path);

  const found = candidates.find((value) => typeof value === "string" && value.trim().length > 0);
  return found ? found.trim() : "";
}

export function s4Health(baseUrl) {
  const response = http.get(`${baseUrl}/api/v1/health`);
  check(response, {
    "S4 health status 200": (r) => r.status === 200,
    "S4 health body ok": (r) => r.json("status") === "ok",
  });
  return response;
}

export function s1TextSearch(baseUrl, config) {
  const query = pickQuery();
  const response = http.post(
    `${baseUrl}/api/v1/text-similarity/search`,
    JSON.stringify({
      query: query.query,
      mktu_codes: query.mktu_codes,
      top_k: config.textTopK,
    }),
    {
      headers: { "Content-Type": "application/json" },
      timeout: __ENV.K6_TEXT_TIMEOUT || "120s",
    },
  );

  check(response, {
    "S1 text status 200": (r) => r.status === 200,
    "S1 text has matches": (r) => Array.isArray(r.json("matches")),
  });

  return response;
}

export function s2LogoSearch(baseUrl, config) {
  const response = http.post(
    `${baseUrl}/api/v1/logo-similarity/search?top_k=${config.logoTopK}`,
    {
      file: http.file(LOGO_BINARY, "sample-logo.png", "image/png"),
    },
    {
      timeout: __ENV.K6_LOGO_TIMEOUT || "300s",
    },
  );

  check(response, {
    "S2 logo status 200": (r) => r.status === 200,
    "S2 logo has matches": (r) => {
      const payload = parseJson(r);
      return !!payload && Array.isArray(payload.matches);
    },
  });

  const payload = parseJson(response);
  return {
    response,
    previewPath: extractPreviewPath(payload),
  };
}

export function s3Preview(baseUrl, previewPath) {
  if (!previewPath) {
    return null;
  }

  const encodedPath = encodeURIComponent(previewPath);
  const response = http.get(`${baseUrl}/api/v1/logo-similarity/preview?logo_path=${encodedPath}`, {
    timeout: __ENV.K6_PREVIEW_TIMEOUT || "60s",
  });

  check(response, {
    "S3 preview status 200": (r) => r.status === 200,
    "S3 preview has body": (r) => (r.body || "").length > 0,
  });

  return response;
}

function pickFlow(config) {
  const weighted = [
    { id: "S1", weight: config.s1Weight },
    { id: "S2", weight: config.s2Weight },
    { id: "S3", weight: config.s3Weight },
    { id: "S4", weight: config.s4Weight },
  ].filter((item) => item.weight > 0);

  const total = weighted.reduce((acc, item) => acc + item.weight, 0);
  if (total <= 0) {
    return "S1";
  }

  let pick = Math.random() * total;
  for (const item of weighted) {
    pick -= item.weight;
    if (pick <= 0) {
      return item.id;
    }
  }

  return weighted[weighted.length - 1].id;
}

export function runMixedIteration(config, state) {
  const flow = pickFlow(config);

  if (flow === "S1") {
    s1TextSearch(config.baseUrl, config);
  } else if (flow === "S2") {
    const logo = s2LogoSearch(config.baseUrl, config);
    state.lastPreviewPath = logo.previewPath || state.lastPreviewPath;
  } else if (flow === "S3") {
    const previewPath = state.lastPreviewPath || config.fallbackPreviewPath;
    if (!previewPath) {
      s4Health(config.baseUrl);
    } else {
      s3Preview(config.baseUrl, previewPath);
    }
  } else {
    s4Health(config.baseUrl);
  }

  sleep(config.iterationSleepSeconds);
}
