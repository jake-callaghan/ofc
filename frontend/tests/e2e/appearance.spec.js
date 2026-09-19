import { test, expect } from '@playwright/test';

test('settings and modern lobby controls work on mobile and desktop', async ({
  page,
}) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Display name').fill('Appearance test');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Lobby', exact: true }),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Join a table' }).click();
  await expect(page.getByLabel('Invitation link')).toBeVisible();
  await page.getByRole('tab', { name: 'Create a table' }).click();
  await expect(page.getByLabel('Table name')).toBeVisible();

  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator('.settings > summary').click();
    await expect(
      page.getByRole('switch', { name: 'Four-colour suits' }),
    ).toBeVisible();
    for (const theme of ['ocean', 'midnight', 'casino']) {
      await page.getByLabel('Colour theme').selectOption(theme);
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await page.keyboard.press('Escape');
    await expect(page.locator('.settings')).not.toHaveAttribute('open');
  }

  await page.locator('.settings > summary').click();
  await page.getByRole('switch', { name: 'Four-colour suits' }).click();
  await expect(
    page.getByRole('switch', { name: 'Four-colour suits' }),
  ).toHaveAttribute('aria-checked', 'false');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download player key' }).click();
  expect((await download).suggestedFilename()).toBe(
    'open-face-player-key.json',
  );
  await page.keyboard.press('Escape');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute(
    'data-suit-colours',
    'two',
  );
  await page.getByLabel('Table name').fill('Modern table');
  await page.getByRole('button', { name: 'Create table →' }).click();
  await expect(
    page.getByRole('heading', { name: 'Modern table' }),
  ).toBeVisible();
  await page.getByText('Table settings', { exact: true }).click();
  await page.getByLabel('Turn timer (seconds)').fill('45');
  await page.getByLabel('Orbit limit').fill('3');
  await page.getByRole('button', { name: 'Save settings' }).click();
  await expect(page.locator('.table-subtitle')).toContainText('45s turns');
  await expect(page.locator('.table-subtitle')).toContainText('3 orbits');
  await page.reload();
  await expect(page.locator('.table-subtitle')).toContainText('45s turns');
  await page.getByRole('button', { name: '← Tables' }).click();
  await page.getByRole('button', { name: 'Modern table', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Modern table' }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test('themes include backgrounds and respect saved motion preferences', async ({
  page,
}) => {
  await page.goto('/');
  await page.locator('.settings > summary').click();
  await expect(page.getByLabel('Background style')).toHaveCount(0);
  await expect(page.locator('html')).toHaveAttribute(
    'data-background',
    'shapes',
  );
  await page.getByLabel('Colour theme').selectOption('ocean');
  await page.getByRole('switch', { name: 'Background motion' }).click();
  await expect(page.locator('html')).toHaveAttribute(
    'data-background-motion',
    'false',
  );
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-background', 'waves');
  await expect(page.locator('.ambient-one')).toHaveCSS(
    'animation-play-state',
    'paused',
  );
  await page.locator('.settings > summary').click();
  await page.getByRole('switch', { name: 'Background motion' }).click();
  for (const [theme, background, animation] of [
    ['ocean', 'waves', 'wave-drift'],
    ['slate', 'shapes', 'shape-drift'],
    ['casino', 'shapes', 'shape-drift'],
  ]) {
    await page.getByLabel('Colour theme').selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute(
      'data-background',
      background,
    );
    await expect(page.locator('.ambient-one')).toHaveCSS(
      'animation-name',
      animation,
    );
    await expect(page.locator('.ambient-one')).toHaveCSS(
      'animation-play-state',
      'running',
    );
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('.ambient-one')).toHaveCSS(
    'animation-name',
    'none',
  );
  await page.getByLabel('Colour theme').selectOption('midnight');
  await expect(page.locator('.ambient-dots')).toHaveCSS(
    'animation-name',
    'none',
  );
  await page.getByLabel('Colour theme').selectOption('slate');
  await expect(page.locator('.ambient-background')).toBeVisible();
  await expect(
    page.getByRole('switch', { name: 'Background motion' }),
  ).toBeVisible();
});
