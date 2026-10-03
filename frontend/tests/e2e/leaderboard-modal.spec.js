import { test, expect } from '@playwright/test';

test('leaderboard opens from lobby and menu, restores focus and keeps table state', async ({
  page,
  request,
}) => {
  const account = await (
    await request.post('/api/players', { data: { name: 'Menu player' } })
  ).json();
  await page.addInitScript(
    (value) => localStorage.setItem('ofc.player', JSON.stringify(value)),
    account,
  );
  await page.goto('/');
  const trigger = page.getByRole('button', {
    name: 'Leaderboard',
    exact: true,
  });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await trigger.click();
  const modal = page.getByRole('dialog', { name: 'Global leaderboard' });
  await expect(modal).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Close leaderboard' }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await page.getByText('Menu', { exact: true }).click();
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: 'Leaderboard' })
    .click();
  await expect(modal).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(modal).toHaveCount(0);
  await expect(page.locator('.settings > summary')).toBeFocused();
  await page.getByText('Menu', { exact: true }).click();
  await page.screenshot({
    path: 'test-results/menu-desktop.png',
    fullPage: true,
  });
  await page.keyboard.press('Escape');

  const game = await (
    await request.post('/api/games', {
      headers: { Authorization: `Bearer ${account.token}` },
      data: { name: 'Keep this table' },
    })
  ).json();
  await page.goto(`/#game=${game.game_id}`);
  await expect(page.getByText('Live table', { exact: true })).toBeVisible();
  await page.getByText('Menu', { exact: true }).click();
  await page.getByRole('button', { name: 'Leaderboard', exact: true }).click();
  await expect(modal).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(modal).toBeVisible();
  expect(
    await modal.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: 'test-results/leaderboard-mobile.png' });
  await page.getByRole('button', { name: 'Close leaderboard' }).click();
  await expect(page).toHaveURL(new RegExp(`game=${game.game_id}`));
  await expect(
    page.getByRole('heading', { name: 'Keep this table' }),
  ).toBeVisible();
  await page.getByText('Menu', { exact: true }).click();
  await page.screenshot({ path: 'test-results/menu-mobile.png' });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
