import { test, expect } from '@playwright/test';

test('a later draw can be arranged early and confirmed when the turn arrives', async ({
  page,
}) => {
  const empty = () => ({ top: [], middle: [], bottom: [] });
  let game = {
    game_id: 'early',
    name: 'Early placement',
    owner: 'a',
    members: ['a', 'b'],
    player_names: { a: 'Alice', b: 'Bob' },
    balances: { a: 0, b: 0 },
    fantasy: { a: 0, b: 0 },
    version: 1,
    hand_number: 1,
    status: 'active',
    rules: { variant: 'pineapple', fantasyland: 'progressive' },
    hand: {
      number: 1,
      status: 'playing',
      players: ['a', 'b'],
      fantasy: { a: 0, b: 0 },
      fantasy_pending: [],
      boards: {
        a: { top: ['2c', '3c', '4c'], middle: ['5c', '6c'], bottom: [] },
        b: empty(),
      },
      discards: { a: [] },
      draws: { a: ['Ac', 'Ad', 'Kd'] },
      draw_keep: 2,
      turn: { player: 'b', keep: 2, draw: 3, street: 1 },
      deadline: null,
    },
  };
  let socket;
  await page.addInitScript(() =>
    localStorage.setItem(
      'ofc.player',
      JSON.stringify({ player_id: 'a', token: 'test', name: 'Alice' }),
    ),
  );
  await page.routeWebSocket('**/api/games/early/events', (ws) => {
    socket = ws;
    ws.onMessage(() =>
      ws.send(JSON.stringify({ type: 'snapshot', state: game })),
    );
  });
  await page.route('**/api/games/early', (route) =>
    route.fulfill({ json: game }),
  );
  const requests = [];
  await page.route('**/api/games/early/commands', async (route) => {
    const body = route.request().postDataJSON();
    requests.push(body);
    game = { ...game, version: 3, hand: { ...game.hand, draws: { a: [] } } };
    await route.fulfill({ json: { state: game, applied_version: 3 } });
  });
  await page.goto('/#game=early');
  await expect(page.getByText('Live table', { exact: true })).toBeVisible();
  await expect(
    page.getByText('Place 2 · discard 1', { exact: true }),
  ).toBeVisible();
  for (let i = 0; i < 2; i++) {
    await page.locator('.draw-cards .card').first().click();
    await page
      .locator('.my-table')
      .getByRole('button', {
        name: 'Place selected card in bottom',
        exact: true,
      })
      .first()
      .click();
  }
  await expect(page.locator('.discard-zone .card')).toHaveCount(1);
  await expect(
    page.getByRole('button', { name: 'Waiting for your turn' }),
  ).toBeDisabled();
  expect(requests).toHaveLength(0);
  game = {
    ...game,
    version: 2,
    hand: { ...game.hand, turn: { player: 'a', keep: 2, draw: 3, street: 1 } },
  };
  socket.send(JSON.stringify({ type: 'snapshot', state: game }));
  await expect(
    page.getByRole('button', { name: 'Confirm placement →' }),
  ).toBeEnabled();
  await expect(page.locator('.discard-zone .card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Confirm placement →' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].command.placements.bottom).toEqual(['Ac', 'Ad']);
  expect(requests[0].command.discards).toEqual(['Kd']);
});
