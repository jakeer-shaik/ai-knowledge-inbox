import { defineConfig } from "@playwright/test";

// End-to-end: real frontend (Vite) -> real backend (FastAPI + worker + SQLite) -> local web pages.
// Only Gemini is replaced (see backend/tests/e2e_server.py). Uses the locally installed Chrome.
const API_PORT = 8100;
const PAGES_PORT = 8200;
const UI_PORT = 5180;

export const PAGES_URL = `http://127.0.0.1:${PAGES_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${UI_PORT}`,
    channel: "chrome",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `../backend/.venv/bin/python ../backend/tests/e2e_server.py --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
    },
    {
      command: `python3 -m http.server ${PAGES_PORT} --bind 127.0.0.1 --directory e2e/pages`,
      url: `${PAGES_URL}/article.html`,
      reuseExistingServer: false,
    },
    {
      command: `npx vite --port ${UI_PORT} --strictPort`,
      url: `http://localhost:${UI_PORT}`,
      env: { API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
    },
  ],
});
