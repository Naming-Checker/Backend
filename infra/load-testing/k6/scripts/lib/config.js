const DEFAULT_BASE_URL = "http://naming-check-backend:8000";

const PROFILE_DEFAULTS = {
  smoke: {
    vus: 1,
    duration: "30s",
    thresholds: {
      http_req_failed: ["rate<0.05"],
      checks: ["rate>0.95"],
      http_req_duration: ["p(95)<60000"],
    },
  },
  baseline: {
    vus: 1,
    duration: "10m",
    thresholds: {
      http_req_failed: ["rate<0.01"],
      checks: ["rate>0.99"],
      http_req_duration: ["p(95)<10000"],
    },
  },
  stress: {
    stages: [
      { duration: "4m", target: 5 },
      { duration: "6m", target: 15 },
      { duration: "6m", target: 30 },
      { duration: "4m", target: 5 },
    ],
    thresholds: {
      http_req_failed: ["rate<0.05"],
      checks: ["rate>0.90"],
      http_req_duration: ["p(95)<30000"],
    },
  },
};

function envNum(name, fallback) {
  const raw = __ENV[name];
  if (!raw) {
    return fallback;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeBaseUrl(url) {
  return (url || DEFAULT_BASE_URL).replace(/\/$/, "");
}

export function getRuntimeConfig(profileName) {
  const profile = profileName || __ENV.LOAD_TEST_PROFILE || "smoke";
  return {
    profile,
    baseUrl: normalizeBaseUrl(__ENV.LOAD_TEST_BASE_URL),
    vus: envNum("LOAD_TEST_VUS", PROFILE_DEFAULTS[profile]?.vus ?? 1),
    duration: __ENV.LOAD_TEST_DURATION || PROFILE_DEFAULTS[profile]?.duration || "1m",
    rps: envNum("LOAD_TEST_RPS", 0),
    iterationSleepSeconds: envNum("LOAD_TEST_ITERATION_SLEEP_SECONDS", 1),
    logoFile: __ENV.K6_LOGO_FILE || "/data/sample-logo.png",
    textTopK: envNum("K6_TEXT_TOP_K", 10),
    logoTopK: envNum("K6_LOGO_TOP_K", 10),
    s1Weight: envNum("LOAD_TEST_S1_WEIGHT", 60),
    s2Weight: envNum("LOAD_TEST_S2_WEIGHT", 25),
    s3Weight: envNum("LOAD_TEST_S3_WEIGHT", 10),
    s4Weight: envNum("LOAD_TEST_S4_WEIGHT", 5),
    fallbackPreviewPath: __ENV.K6_FALLBACK_PREVIEW_PATH || "",
  };
}

export function parseStressStages() {
  const raw = (__ENV.LOAD_TEST_STAGES || "").trim();
  if (!raw) {
    return PROFILE_DEFAULTS.stress.stages;
  }

  const stages = raw
    .split(",")
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      const [duration, target] = chunk.split(":");
      return {
        duration: (duration || "").trim(),
        target: Number((target || "").trim()),
      };
    })
    .filter((stage) => stage.duration && Number.isFinite(stage.target));

  return stages.length ? stages : PROFILE_DEFAULTS.stress.stages;
}

function thresholdKey(prefix, suffix = "") {
  return suffix ? `${prefix}${suffix}` : prefix;
}

export function buildThresholds(profileName, { useScenarioTag = true } = {}) {
  const defaults = PROFILE_DEFAULTS[profileName]?.thresholds || PROFILE_DEFAULTS.smoke.thresholds;
  if (!useScenarioTag) {
    return defaults;
  }

  return {
    [thresholdKey("http_req_failed", '{scenario:mixed}')]: defaults.http_req_failed,
    [thresholdKey("checks", '{scenario:mixed}')]: defaults.checks,
    [thresholdKey("http_req_duration", '{scenario:mixed}')]: defaults.http_req_duration,
  };
}

export function buildConstantVusOptions(profileName, config) {
  const opts = {
    scenarios: {
      mixed: {
        executor: "constant-vus",
        vus: config.vus,
        duration: config.duration,
      },
    },
    thresholds: buildThresholds(profileName),
  };

  if (config.rps > 0) {
    opts.scenarios.mixed.executor = "constant-arrival-rate";
    opts.scenarios.mixed.rate = config.rps;
    opts.scenarios.mixed.timeUnit = "1s";
    opts.scenarios.mixed.preAllocatedVUs = Math.max(config.vus, 5);
    opts.scenarios.mixed.maxVUs = Math.max(config.vus * 4, config.rps * 2, 20);
    delete opts.scenarios.mixed.vus;
  }

  return opts;
}

export function buildStressOptions(config) {
  const stages = parseStressStages();
  return {
    scenarios: {
      mixed: {
        executor: "ramping-vus",
        startVUs: envNum("LOAD_TEST_START_VUS", stages[0]?.target || 1),
        stages,
        gracefulRampDown: "30s",
      },
    },
    thresholds: buildThresholds("stress"),
  };
}

export const profileDefaults = PROFILE_DEFAULTS;
