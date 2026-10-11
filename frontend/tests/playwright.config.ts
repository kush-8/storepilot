import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: '**/storepilot.spec.ts',
  timeout: 20_000,
  expect: { timeout: 3_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.STOREPILOT_URL ?? 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: process.env.STOREPILOT_BROWSER_CHANNEL ?? 'msedge',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: process.env.STOREPILOT_URL ? undefined : {
    command: 'npm --prefix .. run dev -- --host 127.0.0.1 --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: false,
    timeout: 30_000,
  },
})
