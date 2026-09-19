import { test, expect } from '@playwright/test';

test('table members exchange chat and reactions and can hide the panel', async ({
  browser,
}) => {
  const first = await browser.newContext();
  const second = await browser.newContext();
  const owner = await first.newPage();
  const guest = await second.newPage();
  try {
    await owner.goto('/');
    await owner.getByLabel('Display name').fill('Chat owner');
    await owner.getByRole('button', { name: 'Continue', exact: true }).click();
    await owner.getByRole('button', { name: 'Create table →' }).click();
    await owner.getByText('Show invitation', { exact: true }).click();
    const link = await owner.getByLabel('Invitation link').inputValue();
    await guest.goto(link);
    await guest.getByLabel('Display name').fill('Chat guest');
    await guest.getByRole('button', { name: 'Continue', exact: true }).click();
    await guest.getByRole('button', { name: 'Join table →' }).click();
    await expect(
      guest.getByRole('button', { name: 'Open table chat' }),
    ).toBeVisible();
    await owner.getByRole('button', { name: 'Open table chat' }).click();
    await owner.getByLabel('Chat message').fill('Hello <script>');
    await owner.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(guest.getByLabel('Unread messages')).toBeVisible();
    await expect(guest.locator('.chat-toggle')).toHaveCSS(
      'animation-name',
      'none',
    );
    await guest.getByRole('button', { name: 'Open table chat' }).click();
    await expect(guest.locator('.chat-toggle')).toHaveCSS(
      'animation-name',
      'none',
    );
    await expect(
      guest.getByText('Hello <script>', { exact: true }),
    ).toBeVisible();
    await guest.getByLabel('Chat message').fill('Draft stays here');
    await guest.getByRole('button', { name: 'Send 🐟', exact: true }).click();
    await expect(
      owner.locator('.chat-message').filter({ hasText: '🐟' }),
    ).toHaveCount(1);
    await expect(guest.getByLabel('Chat message')).toHaveValue(
      'Draft stays here',
    );
    await guest.getByRole('button', { name: 'Send 🐟', exact: true }).click();
    await expect(
      owner.locator('.chat-message').filter({ hasText: '🐟' }),
    ).toHaveCount(2);
    await owner.getByLabel('Chat message').focus();
    await owner.keyboard.press('Escape');
    await expect(
      owner.getByRole('region', { name: 'Table chat', exact: true }),
    ).toBeHidden();
    await guest.reload();
    await guest.setViewportSize({ width: 390, height: 844 });
    await guest.getByRole('button', { name: 'Open table chat' }).click();
    await expect(
      guest.getByText('Hello <script>', { exact: true }),
    ).toBeVisible();
    expect(
      await guest.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  } finally {
    await first.close();
    await second.close();
  }
});
