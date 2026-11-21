import { test, expect } from '@playwright/test';

const empty = () => ({ top: [], middle: [], bottom: [] });
const fantasyCards = 'Ts Jd 2h 3h 4h 6h 7h Kc Kd Ks 5s 5c 2d 3s 8c'.split(' ');

async function mockTable(
  page,
  { complete = false, fantasy = true, drawCards = fantasyCards } = {},
) {
  const valid = {
    top: ['Ts', 'Jd', '8c'],
    middle: ['2h', '3h', '4h', '6h', '7h'],
    bottom: ['Kc', 'Kd', 'Ks', '5s', '5c'],
  };
  let game = {
    game_id: 'effects',
    name: 'Effects test',
    owner: 'a',
    members: ['a', 'b'],
    player_names: { a: 'Alice', b: 'Bob' },
    balances: { a: 14, b: -14 },
    fantasy: { a: 0, b: 0 },
    version: 1,
    hand_number: 1,
    status: 'active',
    rules: { variant: 'pineapple', fantasyland: 'progressive', moon: true },
    chat: [{ id: 'old', player: 'b', name: 'Bob', text: '🐟', created_at: 1 }],
    hand: {
      number: 1,
      status: complete ? 'complete' : 'playing',
      players: ['a', 'b'],
      fantasy: { a: fantasy ? 15 : 0, b: 0 },
      fantasy_pending: !complete && fantasy ? ['a'] : [],
      boards: { a: complete ? valid : empty(), b: empty() },
      discards: { a: [] },
      draws: { a: complete ? [] : drawCards },
      turn: { player: 'a', keep: 13, draw: 15 },
      deadline: null,
      result: complete
        ? {
            units: { a: 14, b: -14 },
            evaluations: {
              a: {
                foul: false,
                ranks: {
                  top: [0, 11, 10, 8, 0, 0],
                  middle: [5, 7, 6, 4, 3, 2],
                  bottom: [6, 13, 5, 0, 0, 0],
                },
              },
              b: {
                foul: false,
                ranks: {
                  top: [0, 10, 8, 6, 0, 0],
                  middle: [4, 6, 0, 0, 0, 0],
                  bottom: [6, 14, 2, 0, 0, 0],
                },
              },
            },
            pairs: [
              {
                a: 'a',
                b: 'b',
                rows: 1,
                scoop: 0,
                foul: 0,
                royalties: 13,
                special: 0,
                total: 14,
              },
            ],
          }
        : null,
    },
  };
  let socket;
  await page.addInitScript(() =>
    localStorage.setItem(
      'ofc.player',
      JSON.stringify({ player_id: 'a', token: 'test', name: 'Alice' }),
    ),
  );
  await page.route('**/api/auth/config', (route) =>
    route.fulfill({ json: { legacy: true, enabled: false } }),
  );
  await page.route('**/api/games/effects', (route) =>
    route.fulfill({ json: game }),
  );
  await page.routeWebSocket('**/api/games/effects/events', (ws) => {
    socket = ws;
    ws.onMessage(() =>
      ws.send(JSON.stringify({ type: 'snapshot', state: game })),
    );
  });
  await page.route('**/api/games/effects/hands?**', (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto('/#game=effects');
  await expect(page.getByText('Live table', { exact: true })).toBeVisible();
  return {
    message(text, id) {
      game = {
        ...game,
        chat: [
          ...game.chat,
          { id, player: 'b', name: 'Bob', text, created_at: Date.now() / 1000 },
        ],
      };
      socket.send(JSON.stringify({ type: 'snapshot', state: game }));
    },
  };
}

async function place(page, card, row) {
  await page
    .locator('.draw-cards')
    .getByRole('button', { name: card, exact: true })
    .click();
  await page
    .locator('.my-table')
    .getByRole('button', { name: `Place selected card in ${row}`, exact: true })
    .first()
    .click();
}

test('live royalties warn without losing cards, then celebrate a repaired fantasyland board', async ({
  page,
}, testInfo) => {
  await mockTable(page);
  await expect(page.locator('.fantasyland-entry')).toHaveCount(1);
  for (const card of ['K of clubs', 'K of diamonds', 'K of spades'])
    await place(page, card, 'top');
  for (const card of [
    '2 of hearts',
    '3 of hearts',
    '4 of hearts',
    '6 of hearts',
    '7 of hearts',
  ])
    await place(page, card, 'middle');
  for (const card of [
    '5 of spades',
    '5 of clubs',
    '10 of spades',
    'J of diamonds',
    '8 of clubs',
  ])
    await place(page, card, 'bottom');
  await expect(page.locator('.placement-feedback')).toContainText(
    'Bottom must be at least as strong as middle.',
  );
  await expect(page.locator('.row-invalid')).toHaveCount(1);
  await expect(page.locator('.my-table .board .card')).toHaveCount(13);
  await expect(
    page.getByRole('button', { name: 'Confirm placement →' }),
  ).toBeEnabled();
  await page.screenshot({
    path: testInfo.outputPath('fouled-board.png'),
    fullPage: true,
    animations: 'disabled',
  });
  for (const card of [
    'K of clubs',
    'K of diamonds',
    'K of spades',
    '10 of spades',
    'J of diamonds',
    '8 of clubs',
  ]) {
    await page
      .locator('.board')
      .getByRole('button', {
        name: `${card}, pending placement, click to return`,
        exact: true,
      })
      .click();
  }
  for (const card of ['10 of spades', 'J of diamonds', '8 of clubs'])
    await place(page, card, 'top');
  for (const card of ['K of clubs', 'K of diamonds', 'K of spades'])
    await place(page, card, 'bottom');
  await expect(page.locator('.placement-feedback')).toContainText(
    'Back to valid! Valid board · +14',
  );
  await expect(page.locator('.row-invalid')).toHaveCount(0);
  await expect(page.locator('.board-recovered')).toHaveCount(1);
  await expect(
    page.getByLabel('middle: Flush, 8 provisional royalty units'),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1600 });
  await page.evaluate(() => scrollTo(0, 0));
  const source = await page
    .locator('.discard-zone .card')
    .first()
    .boundingBox();
  const destination = await page
    .locator('.my-table .board-row')
    .first()
    .boundingBox();
  await page.mouse.move(
    source.x + source.width / 2,
    source.y + source.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    destination.x + destination.width / 2,
    destination.y + destination.height / 2,
    { steps: 6 },
  );
  await page.mouse.up();
  await expect(page.locator('.placement-feedback')).toContainText(
    'Top is full.',
  );
  await expect(page.locator('.my-table .board .card')).toHaveCount(13);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath('royalty-preview-mobile.png'),
    fullPage: true,
    animations: 'disabled',
  });
});

test('chat effects use fresh messages, cooldowns, smile moon and persistent effects preference', async ({
  page,
}, testInfo) => {
  await page.clock.install();
  const table = await mockTable(page);
  await page.getByRole('button', { name: 'Open table chat' }).click();
  await expect(page.locator('.chat-effect')).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Send 🌝', exact: true }),
  ).toBeVisible();
  table.message('🌝', 'moon');
  await expect(page.locator('.chat-effect-moon')).toHaveCount(1);
  await page.screenshot({
    path: testInfo.outputPath('smile-moon.png'),
    animations: 'disabled',
  });
  table.message('🚀', 'cooldown');
  await expect(page.locator('.chat-message')).toHaveCount(3);
  await expect(page.locator('.chat-effect-rocket')).toHaveCount(0);
  await page.clock.runFor(2700);
  table.message('👏', 'clap');
  await expect(page.locator('.chat-effect-clap')).toHaveCount(1);
  await page.getByRole('button', { name: 'Close table chat' }).click();
  table.message('🐟', 'closed');
  await page.getByRole('button', { name: 'Open table chat' }).click();
  await expect(page.locator('.chat-effect')).toHaveCount(0);
  await page.getByRole('button', { name: 'Close table chat' }).click();
  await page.locator('.settings > summary').click();
  await page.getByRole('switch', { name: 'Effects', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-effects', 'false');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-effects', 'false');
  await page.getByRole('button', { name: 'Open table chat' }).click();
  table.message('🍬', 'disabled');
  await expect(page.locator('.chat-effect')).toHaveCount(0);
});

test('showdown reveals rows and finishes count-up; reduced motion shows final scores immediately', async ({
  page,
}) => {
  await mockTable(page, { complete: true, fantasy: false });
  await expect(page.locator('.showdown-row-result').first()).toBeHidden();
  await expect(
    page.locator('.result-units strong').first().locator('span').last(),
  ).toHaveCSS('font-size', '26px');
  const scoreColour = await page
    .locator('.result-units strong')
    .first()
    .evaluate((element) => getComputedStyle(element).color);
  await expect(
    page.locator('.result-units strong').first().locator('span').last(),
  ).toHaveCSS('color', scoreColour);
  await page.getByText('Row-by-row comparison', { exact: true }).click();
  await expect(page.locator('.showdown-row-result')).toHaveCount(3);
  await expect(page.locator('.showdown-row-result').first()).toContainText(
    'Alice · +1',
  );
  await expect(page.locator('.result-units strong').first()).toHaveText(
    '+14 units',
  );
  await expect(page.locator('.showdown-board').first()).toHaveCount(1);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('html')).toHaveAttribute('data-effects', 'false');
  await expect(page.locator('.showdown-board .board-row').first()).toHaveCSS(
    'animation-name',
    'none',
  );
  await expect(page.locator('.result-units strong').first()).toHaveText(
    '+14 units',
  );
});

test('royalty names fit above the cards at desktop and narrow phone widths', async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mockTable(page, {
    drawCards: '2c 3c 4c 5c 6c 7c 8c 9c Tc Jc Qc Kc Ac 2d'.split(' '),
  });
  for (const [row, names] of [
    ['top', ['2', '3', '4']],
    ['middle', ['5', '6', '7', '8', '9']],
    ['bottom', ['10', 'J', 'Q', 'K', 'A']],
  ])
    for (const name of names) await place(page, `${name} of clubs`, row);
  await expect(
    page.getByLabel('middle: Straight flush, 30 provisional royalty units'),
  ).toBeVisible();
  for (const theme of ['casino', 'arcade']) {
    await page.locator('.settings > summary').click();
    await page.getByLabel('Colour theme').selectOption(theme);
    await page.keyboard.press('Escape');
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      const fits = await page
        .locator('.royalty-preview')
        .evaluateAll((labels) =>
          labels.every((label) => {
            const row = label.closest('.board-row').getBoundingClientRect();
            const text = label.getBoundingClientRect();
            return (
              label.scrollWidth <= label.clientWidth &&
              text.left >= row.left &&
              text.right <= row.right + 1
            );
          }),
        );
      expect(fits).toBe(true);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  }
  await page.screenshot({
    path: testInfo.outputPath('royalty-labels-narrow.png'),
    fullPage: true,
    animations: 'disabled',
  });
});
