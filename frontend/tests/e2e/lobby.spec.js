import { test, expect } from '@playwright/test';

async function player(request, name) {
  const response = await request.post('/api/players', { data: { name } });
  expect(response.ok()).toBeTruthy();
  return response.json();
}
async function signIn(page, account) {
  await page.addInitScript(
    (value) => localStorage.setItem('ofc.player', JSON.stringify(value)),
    account,
  );
}

test('open and private tables are visible; only open tables allow a lobby join', async ({
  page,
  request,
}) => {
  const host = await player(request, 'Lobby host');
  const guest = await player(request, 'Lobby guest');
  const headers = { Authorization: `Bearer ${host.token}` };
  const open = await (
    await request.post('/api/games', {
      headers,
      data: { name: 'Public lobby table' },
    })
  ).json();
  const privateTable = await (
    await request.post('/api/games', {
      headers,
      data: { name: 'Private lobby table', visibility: 'private' },
    })
  ).json();
  await signIn(page, guest);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(
    page.getByRole('button', { name: 'View Private lobby table', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Join Private lobby table', exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Join Public lobby table', exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: 'test-results/lobby-mobile.png',
    fullPage: true,
  });
  await page
    .getByRole('button', { name: 'View Private lobby table', exact: true })
    .click();
  await expect(page.getByText('Live table', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Join table', exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Leave table', exact: true }),
  ).toHaveCount(0);
  const view = await (
    await request.get(`/api/games/${privateTable.game_id}`, {
      headers: { Authorization: `Bearer ${guest.token}` },
    })
  ).json();
  expect(view.members).not.toContain(guest.player_id);
  await page.getByRole('button', { name: '← Tables', exact: true }).click();
  await page
    .getByRole('button', { name: 'Join Public lobby table', exact: true })
    .click();
  await expect(
    page.getByRole('button', { name: 'Leave table', exact: true }),
  ).toBeVisible();
  const joined = await (
    await request.get(`/api/games/${open.game_id}`, { headers })
  ).json();
  expect(joined.members).toContain(guest.player_id);
});

test('new tables default open and the owner can change access', async ({
  page,
  request,
}) => {
  const host = await player(request, 'Settings host');
  await signIn(page, host);
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Recent tables' }),
  ).toHaveCount(0);
  await expect(page.getByLabel('Table access')).toHaveCount(0);
  await page.getByRole('button', { name: 'Create table', exact: true }).click();
  await expect(page.getByLabel('Table access')).toHaveValue('open');
  await page
    .getByLabel('Table name', { exact: true })
    .fill('Access settings table');
  await page.getByLabel('Table access').selectOption('private');
  await page
    .getByRole('button', { name: 'Create table →', exact: true })
    .click();
  await expect(page.getByText('Live table', { exact: true })).toBeVisible();
  await page.getByText('Table settings', { exact: true }).click();
  await expect(page.getByLabel('Table access')).toHaveValue('private');
  await page.getByLabel('Table access').selectOption('open');
  await page
    .getByRole('button', { name: 'Save settings', exact: true })
    .click();
  await expect(page.locator('.table-subtitle')).toContainText('Open');
  await page.getByRole('button', { name: '← Tables', exact: true }).click();
  await expect(
    page.getByRole('row').filter({ hasText: 'Access settings table' }),
  ).toContainText('Open');
});
