import { buildStressOptions, getRuntimeConfig } from "./lib/config.js";
import { runMixedIteration } from "./lib/flows.js";
import { buildSummary } from "./lib/summary.js";

const config = getRuntimeConfig("stress");
const state = {
  lastPreviewPath: "",
};

export const options = buildStressOptions(config);

export default function () {
  runMixedIteration(config, state);
}

export const handleSummary = buildSummary({
  profileName: "Stress",
  baseUrl: config.baseUrl,
});
