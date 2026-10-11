import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: '**/storepilot.integration.spec.ts',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:15173',
    browserName: 'chromium',
    channel: process.env.STOREPILOT_BROWSER_CHANNEL ?? 'msedge',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: process.platform === 'win32'
        ? '..\\..\\backend\\.venv\\Scripts\\python.exe -m uvicorn tests.browser_server:app --app-dir ../../backend --host 127.0.0.1 --port 18000'
        : '../../backend/.venv/bin/python -m uvicorn tests.browser_server:app --app-dir ../../backend --host 127.0.0.1 --port 18000',
      url: 'http://127.0.0.1:18000/api/health',
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: 'npm --prefix .. run dev -- --host 127.0.0.1 --port 15173 --strictPort',
      env: { STOREPILOT_API_TARGET: 'http://127.0.0.1:18000' },
      url: 'http://127.0.0.1:15173',
      timeout: 30_000,
      reuseExistingServer: false,
    },
  ],
})
