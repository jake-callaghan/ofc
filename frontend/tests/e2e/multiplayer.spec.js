import { test, expect } from '@playwright/test';

async function register(page, name) {
  await page.goto('/');
  await page.getByLabel('Display name').fill(name);
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Tables' })).toBeVisible();
}
async function state(page) {
  return page.evaluate(async () => {
    const identity = JSON.parse(localStorage.getItem('ofc.player'));
    const id = new URLSearchParams(location.hash.slice(1)).get('game');
    return (
      await fetch(`/api/games/${id}`, {
        headers: { Authorization: `Bearer ${identity.token}` },
      })
    ).json();
  });
}

test('two players join, place a complete pineapple hand, and reconnect', async ({
  browser,
}) => {
  const a = await browser.newContext({
    baseURL: 'http://127.0.0.1:5174',
    viewport: { width: 1440, height: 1000 },
  });
  const b = await browser.newContext({
    baseURL: 'http://127.0.0.1:5174',
    viewport: { width: 390, height: 844 },
  });
  const alice = await a.newPage(),
    bob = await b.newPage();
  const errors = [];
  alice.on('pageerror', (e) => errors.push(e.message));
  bob.on('pageerror', (e) => errors.push(e.message));
  await register(alice, 'Alice');
  await alice.getByLabel('Table name').fill('Sunday Pineapple');
  await alice.getByRole('button', { name: 'Create table →' }).click();
  await expect(
    alice.getByRole('heading', { name: 'Sunday Pineapple' }),
  ).toBeVisible();
  await alice.getByText('Show invitation').click();
  const invitation = await alice.getByLabel('Invitation link').inputValue();
  await bob.goto(invitation);
  await bob.getByLabel('Display name').fill('Bob');
  await bob.getByRole('button', { name: 'Continue' }).click();
  await bob.getByRole('button', { name: 'Join table →' }).click();
  await expect(
    bob.getByRole('heading', { name: 'Sunday Pineapple' }),
  ).toBeVisible();
  await expect(alice.getByLabel('Bob', { exact: true })).toBeVisible();
  await alice.getByRole('button', { name: 'Deal next hand →' }).click();
  await expect(bob.getByText('● Your turn', { exact: true })).toBeVisible();
  await bob.reload();
  await expect(bob.getByText('● Your turn', { exact: true })).toBeVisible();
  const aliceId = await alice.evaluate(
    () => JSON.parse(localStorage.getItem('ofc.player')).player_id,
  );
  const bobId = await bob.evaluate(
    () => JSON.parse(localStorage.getItem('ofc.player')).player_id,
  );
  let current = await state(alice);
  for (let turn = 0; current.hand.status !== 'complete' && turn < 20; turn++) {
    const id = current.hand.turn.player;
    const page = id === aliceId ? alice : bob;
    await expect(page.getByText('● Your turn', { exact: true })).toBeVisible();
    const own = await state(page);
    expect(Object.keys(own.hand.draws)).toEqual([id]);
    expect(own.hand.deck).toBeUndefined();
    const keep = own.hand.turn.keep;
    const board = structuredClone(own.hand.boards[id]);
    for (let card = 0; card < own.hand.draws[id].length; card++) {
      await page.locator('.draw-cards .card').first().click();
      if (card < keep) {
        const row = Object.keys(board).find(
          (row) => board[row].length < (row === 'top' ? 3 : 5),
        );
        await page
          .locator('.my-table')
          .getByRole('button', {
            name: `Place selected card in ${row}`,
            exact: true,
          })
          .first()
          .click();
        board[row].push('placed');
      } else
        await page
          .getByRole('button', { name: 'Discard selected card' })
          .click();
    }
    if (turn === 0) {
      await page.screenshot({
        path: 'test-results/mobile-placement.png',
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await page.getByRole('button', { name: 'Confirm placement →' }).click();
    await expect
      .poll(async () => (await state(page)).version)
      .toBeGreaterThan(own.version);
    current = await state(alice);
  }
  expect(current.hand.status).toBe('complete');
  expect(current.balances[aliceId] + current.balances[bobId]).toBe(0);
  await expect(
    alice.getByRole('heading', { name: 'Hand 1 results' }),
  ).toBeVisible();
  await alice.screenshot({
    path: 'test-results/desktop-results.png',
    fullPage: true,
  });
  await alice.getByRole('button', { name: /Hand history/ }).click();
  await expect(
    alice.getByRole('heading', { name: 'Hand history' }),
  ).toBeVisible();
  await alice.locator('.history summary').first().click();
  await expect(alice.locator('.history-boards')).toBeVisible();
  expect(errors).toEqual([]);
  await a.close();
  await b.close();
});

test('classic rules and the lobby fit a mobile screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page, 'Charlie');
  await page.getByRole('button', { name: /Classic OFC/ }).click();
  await expect(page.getByLabel('Fantasyland', { exact: true })).toHaveValue(
    'standard',
  );
  await expect(page.getByText('2–4 active players')).toBeVisible();
  await page.screenshot({
    path: 'test-results/mobile-lobby.png',
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
