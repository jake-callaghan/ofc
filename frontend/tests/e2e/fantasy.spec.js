import { test, expect } from '@playwright/test';

for (const normalActive of [true, false]) {
  test(`fantasy confirms independently with normal play ${normalActive ? 'active' : 'finished'}`, async ({
    page,
  }) => {
    const empty = () => ({ top: [], middle: [], bottom: [] });
    let game = {
      game_id: 'fantasy',
      name: 'Independent Fantasyland',
      owner: 'a',
      members: ['a', 'b'],
      player_names: { a: 'Alice', b: 'Bob' },
      balances: { a: 0, b: 0 },
      fantasy: { a: 14, b: 0 },
      version: 1,
      hand_number: 1,
      status: 'active',
      rules: {
        variant: 'pineapple',
        fantasyland: 'progressive',
        turn_seconds: 30,
      },
      hand: {
        number: 1,
        status: 'playing',
        players: ['a', 'b'],
        fantasy: { a: 14, b: 0 },
        fantasy_pending: ['a'],
        boards: { a: empty(), b: empty() },
        discards: { a: [] },
        draws: {
          a: [
            '2c',
            '3c',
            '4c',
            '5c',
            '6c',
            '7c',
            '8c',
            '9c',
            'Tc',
            'Jc',
            'Qc',
            'Kc',
            'Ac',
            '2d',
          ],
        },
        turn: normalActive ? { player: 'b', keep: 2, draw: 3 } : null,
        deadline: normalActive ? 1 : null,
      },
    };
    await page.addInitScript(() =>
      localStorage.setItem(
        'ofc.player',
        JSON.stringify({ player_id: 'a', token: 'test', name: 'Alice' }),
      ),
    );
    await page.routeWebSocket('**/api/games/fantasy/events', (socket) => {
      socket.onMessage(() =>
        socket.send(JSON.stringify({ type: 'snapshot', state: game })),
      );
    });
    await page.route('**/api/games/fantasy', (route) =>
      route.fulfill({ json: game }),
    );
    const requests = [];
    await page.route('**/api/games/fantasy/commands', async (route) => {
      const body = route.request().postDataJSON();
      requests.push(body);
      if (requests.length === 1) {
        game = { ...game, version: 2 };
        await route.fulfill({ status: 409, json: { detail: 'stale version' } });
      } else {
        game = {
          ...game,
          version: 3,
          hand: {
            ...game.hand,
            fantasy_pending: [],
            draws: { a: [] },
            boards: { ...game.hand.boards, a: body.command.placements },
          },
        };
        await route.fulfill({ json: { state: game, applied_version: 3 } });
      }
    });
    await page.goto('/#game=fantasy');
    await expect(page.getByText('Live table', { exact: true })).toBeVisible();
    await expect(page.locator('.turn-banner')).toHaveText(
      'Arrange your Fantasyland board and confirm when ready',
    );
    for (const [row, count] of [
      ['top', 3],
      ['middle', 5],
      ['bottom', 5],
    ]) {
      for (let i = 0; i < count; i++) {
        await page.locator('.draw-cards .card').first().click();
        await page
          .locator('.my-table')
          .getByRole('button', {
            name: `Place selected card in ${row}`,
            exact: true,
          })
          .first()
          .click();
      }
    }
    await page.getByRole('button', { name: 'Confirm placement →' }).click();
    await expect(page.locator('.turn-banner')).toHaveText(
      'Board confirmed · waiting for showdown',
    );
    expect(requests).toHaveLength(2);
    expect(requests[1].version).toBe(2);
    expect(requests[1].request_id).toBe(requests[0].request_id);
    expect(requests[1].command).toEqual(requests[0].command);
    expect(requests[1].command.discards).toHaveLength(1);
  });
}
