import { test, expect } from '@playwright/test';

test('GBP settings, visible history and host closure work together', async ({
  page,
  request,
}) => {
  const accounts = [];
  for (const name of ['GBP host', 'GBP guest']) {
    accounts.push(
      await (await request.post('/api/players', { data: { name } })).json(),
    );
  }
  const [host, guest] = accounts;
  const headers = { Authorization: `Bearer ${host.token}` };
  await page.addInitScript(
    (account) => localStorage.setItem('ofc.player', JSON.stringify(account)),
    host,
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Create table', exact: true }).click();
  await expect(
    page.getByRole('button', { name: '10p', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByLabel('Count towards the global leaderboard'),
  ).toBeChecked();
  await page.getByRole('button', { name: '50p', exact: true }).click();
  await page.getByLabel('Table name', { exact: true }).fill('GBP test table');
  await page
    .getByRole('combobox', { name: 'Fantasyland', exact: true })
    .selectOption('off');
  await page
    .getByRole('button', { name: 'Create table →', exact: true })
    .click();
  await expect(page.getByText('Live table', { exact: true })).toBeVisible();
  const gid = await page.evaluate(
    () =>
      JSON.parse(
        localStorage.getItem(
          `ofc.tables.${JSON.parse(localStorage.getItem('ofc.player')).player_id}`,
        ),
      )[0].id,
  );
  const url = `/api/games/${gid}`;
  async function state() {
    return (await request.get(url, { headers })).json();
  }
  async function command(actor, current, move) {
    const response = await request.post(`${url}/commands`, {
      headers: { Authorization: `Bearer ${actor.token}` },
      data: {
        request_id: crypto.randomUUID(),
        version: current.version,
        command: move,
      },
    });
    expect(response.ok()).toBeTruthy();
    return response.json();
  }
  await request.post(`${url}/join`, {
    headers: { Authorization: `Bearer ${guest.token}` },
    data: { request_id: 'join' },
  });
  await command(host, await state(), {
    type: 'start',
    players: accounts.map((a) => a.player_id),
  });
  let current = await state();
  await expect(page.locator('.draw-cards .card')).toHaveCount(5);
  await page.locator('.draw-cards .card').first().click();
  await page
    .getByRole('button', { name: 'Place selected card in bottom', exact: true })
    .first()
    .click();
  await expect(page.locator('.my-table .board .draft-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Hand history', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Hand history', exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`game=${gid}`));
  await expect(page.locator('.my-table .board .draft-card')).toHaveCount(1);
  await expect(
    page.getByRole('button', { name: 'Leave table', exact: true }),
  ).toBeDisabled();
  while (current.hand.status === 'playing') {
    const actor = accounts.find(
      (a) => a.player_id === current.hand.turn.player,
    );
    const own = await (
      await request.get(url, {
        headers: { Authorization: `Bearer ${actor.token}` },
      })
    ).json();
    const draw = own.hand.draws[actor.player_id];
    const board = own.hand.boards[actor.player_id];
    const placements = { top: [], middle: [], bottom: [] };
    for (const card of draw.slice(0, own.hand.turn.keep)) {
      const row = Object.keys(placements).find(
        (r) => board[r].length + placements[r].length < (r === 'top' ? 3 : 5),
      );
      placements[row].push(card);
    }
    await command(actor, own, {
      type: 'place',
      placements,
      discards: draw.slice(own.hand.turn.keep),
    });
    current = await state();
  }
  await expect(page.locator('.history summary')).toHaveCount(1);
  await page.locator('.history summary').click();
  await expect(page.locator('.history-boards')).toBeVisible();
  expect(current.gbp_balances[host.player_id]).toBe(
    current.balances[host.player_id] * 50,
  );
  await page.getByText('Table settings', { exact: true }).click();
  await page.getByRole('button', { name: '£1', exact: true }).click();
  await page.getByLabel('Count towards the global leaderboard').uncheck();
  await page
    .getByRole('button', { name: 'Save settings', exact: true })
    .click();
  await expect(page.locator('.table-subtitle')).toContainText(
    '£1/unit · Unranked',
  );
  await expect(page.locator('.history')).toContainText('50p/unit');
  await page.screenshot({
    path: 'test-results/table-gbp-history.png',
    fullPage: true,
  });
  const oldTotals = (await state()).gbp_balances;
  expect(oldTotals).toEqual(current.gbp_balances);
  await page.getByRole('button', { name: 'Leave table', exact: true }).click();
  await page
    .getByRole('button', { name: 'Close table & leave', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Lobby', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.active-tables')).not.toContainText(
    'GBP test table',
  );
  await expect(page.locator('.leaderboard')).toContainText('GBP host');
  await page.screenshot({
    path: 'test-results/lobby-desktop.png',
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: 'test-results/lobby-gbp-mobile.png',
    fullPage: true,
  });
  expect((await state()).status).toBe('closed');
});
