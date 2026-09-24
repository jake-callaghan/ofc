import { test, expect } from '@playwright/test';

const profile = {
  player_id: 'account-a',
  name: 'Alice',
  email: 'alice@example.com',
  providers: ['email'],
  recovery: false,
};

async function setup(page, initial = null) {
  let session = initial;
  const requests = [];
  await page.route('**/api/auth/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body =
      route.request().method() === 'POST'
        ? route.request().postDataJSON()
        : null;
    if (body) requests.push({ path, body });
    if (path.endsWith('/config'))
      return route.fulfill({ json: { enabled: true, legacy: false } });
    if (path.endsWith('/session'))
      return route.fulfill(
        session
          ? { json: session }
          : { status: 401, json: { detail: 'Please sign in.' } },
      );
    if (path.endsWith('/login')) {
      session = profile;
      return route.fulfill({ json: profile });
    }
    if (path.endsWith('/logout')) {
      session = null;
      return route.fulfill({ json: { ok: true } });
    }
    if (path.endsWith('/signup')) {
      session = profile;
      return route.fulfill({ json: profile });
    }
    if (path.endsWith('/password')) {
      session = null;
      return route.fulfill({
        json: {
          message: 'Password saved. Sign in with your email and new password.',
        },
      });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  return requests;
}

test('email login persists through reload without storing a player key, then logs out', async ({
  page,
}) => {
  await setup(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Sign in', exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: 'test-results/login-mobile.png',
    fullPage: true,
  });
  await expect(page.getByRole('button', { name: /Google|Forgot password/ })).toHaveCount(0);
  await page.getByLabel('Email', { exact: true }).fill('alice@example.com');
  await page.getByLabel('Password', { exact: true }).fill('correct-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Lobby', exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => localStorage.getItem('ofc.player')),
  ).toBeNull();
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Lobby', exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Sign in', exact: true }),
  ).toBeVisible();
});

test('email signup signs in immediately without confirmation', async ({ page }) => {
  const requests = await setup(page);
  await page.goto('/');
  await page
    .getByRole('button', { name: 'Create an account', exact: true })
    .click();
  await page.getByLabel('Display name', { exact: true }).fill('Alice');
  await page.getByLabel('Email', { exact: true }).fill('alice@example.com');
  await page.getByLabel('Password', { exact: true }).fill('correct-password');
  await page
    .getByRole('button', { name: 'Create account', exact: true })
    .click();
  await expect(page.getByRole('heading', { name: 'Lobby', exact: true })).toBeVisible();
  expect(requests.map((r) => r.path)).toEqual(['/api/auth/signup']);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Lobby', exact: true })).toBeVisible();
});

test('signed-in players can change their password', async ({
  page,
}) => {
  const requests = await setup(page, profile);
  await page.goto('/');
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await page
    .getByLabel('New password', { exact: true })
    .fill('my-new-password');
  await page
    .getByLabel('Confirm new password', { exact: true })
    .fill('my-new-password');
  await page.getByRole('button', { name: 'Save password' }).click();
  await expect(
    page.getByRole('heading', { name: 'Sign in', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Password saved');
  expect(requests[0].path).toBe('/api/auth/password');
});

test('account offers password changes without Google', async ({ page }) => {
  await setup(page, profile);
  await page.goto('/');
  await page.getByRole('button', { name: 'Account', exact: true }).click();
  await expect(page.getByLabel('New password', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Google|Forgot password/ })).toHaveCount(0);
});
