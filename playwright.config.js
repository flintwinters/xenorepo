const { defineConfig, devices } = require("@playwright/test");

const baseURL = process.env.BASE_URL || "http://127.0.0.1:8000";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
const launchOptions = executablePath ? { executablePath } : {};
const retainEvidence = process.env.PLAYWRIGHT_RETAIN_EVIDENCE === "1";
const outputDir = process.env.PLAYWRIGHT_OUTPUT_DIR || "apps/rps/data/ui-check/test-results";

module.exports = defineConfig({
  testDir: ".",
  outputDir,
  forbidOnly: Boolean(process.env.CI),
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: retainEvidence ? "on" : "retain-on-failure",
    video: retainEvidence ? "on" : "retain-on-failure",
    recordHar: retainEvidence ? { path: `${outputDir}/network.har`, mode: "full", content: "embed" } : undefined,
  },
  projects: [
    { name: "wide-viewport-chromium", use: { browserName: "chromium", launchOptions, viewport: { width: 1280, height: 900 } } },
    { name: "narrow-viewport-chromium", use: { ...devices["iPhone 13"], browserName: "chromium", launchOptions } },
  ],
});
