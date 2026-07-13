import { buildConstantVusOptions, getRuntimeConfig } from "./lib/config.js";
import { runMixedIteration } from "./lib/flows.js";
import { buildSummary } from "./lib/summary.js";

const config = getRuntimeConfig("baseline");
const state = {
  lastPreviewPath: "",
};

export const options = buildConstantVusOptions("baseline", config);

export default function () {
  runMixedIteration(config, state);
}

export const handleSummary = buildSummary({
  profileName: "Baseline",
  baseUrl: config.baseUrl,
});
