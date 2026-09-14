import { defineConfig } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 90000,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5174',
    headless: true,
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command:
        'uv run --directory ../server uvicorn ofc.api:app --host 127.0.0.1 --port 8011',
      url: 'http://127.0.0.1:8011/health',
      env: {
        OFC_DATABASE_URL: `sqlite:///${join(tmpdir(), `ofc-e2e-${process.pid}.sqlite3`)}`,
      },
      reuseExistingServer: false,
    },
    {
      command: 'pnpm dev --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      env: { OFC_API_TARGET: 'http://127.0.0.1:8011' },
      reuseExistingServer: false,
    },
  ],
});
