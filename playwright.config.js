import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;

export default defineConfig({
  testDir: "tests",
  // The release test changes what the shared server returns for sw.js.
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}/tl-reader/`,
    trace: "retain-on-failure",
  },
  // Firefox for Android is the target; Chromium covers Chrome on Android.
  projects: [
    { name: "firefox", use: { ...devices["Desktop Firefox"], viewport: { width: 412, height: 860 } } },
    { name: "chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: "node tests/serve.js",
    env: { PORT: String(PORT) },
    url: `http://localhost:${PORT}/tl-reader/`,
    reuseExistingServer: !process.env.CI,
  },
});
