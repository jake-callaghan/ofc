import { invitation } from '../src/lib/navigation.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  assignCard,
  capacity,
  emptyBoard,
  placement,
  pendingAction,
  proposeDiscards,
} from '../src/lib/game.js';

test('a complete pineapple turn requires two placements and one discard', () => {
  const draw = ['Ac', 'Kd', '2h'];
  assert.equal(
    placement(draw, { Ac: 'bottom', Kd: 'middle' }, 2, emptyBoard()),
    null,
  );
  assert.deepEqual(
    placement(
      draw,
      { Ac: 'bottom', Kd: 'middle', '2h': 'discard' },
      2,
      emptyBoard(),
    ),
    {
      type: 'place',
      placements: { top: [], middle: ['Kd'], bottom: ['Ac'] },
      discards: ['2h'],
    },
  );
});
test('overfilling a row leaves the draft intact', () => {
  const board = { ...emptyBoard(), top: ['Ac', 'Kd', 'Qh'] };
  const draft = { '2c': 'middle' };
  assert.equal(assignCard(draft, '2c', 'top', board), draft);
  assert.deepEqual(assignCard(draft, '2c', null, board), {});
});
test('moving a draft card accounts for its old position', () => {
  const board = { ...emptyBoard(), top: ['Ac', 'Kd'] };
  assert.deepEqual(assignCard({ Qh: 'top' }, 'Qh', 'top', board), {
    Qh: 'top',
  });
});
test('foreign cards and excess discards cannot be submitted', () => {
  assert.equal(
    placement(['Ac'], { Ac: 'top', Kd: 'bottom' }, 1, emptyBoard()),
    null,
  );
  assert.equal(placement(['Ac'], { Ac: 'discard' }, 1, emptyBoard()), null);
});
test('fantasyland validates 13 cards and four discards', () => {
  const draw = Array.from({ length: 17 }, (_, i) => `card${i}`);
  const draft = Object.fromEntries(
    draw.map((card, i) => [
      card,
      i < 3 ? 'top' : i < 8 ? 'middle' : i < 13 ? 'bottom' : 'discard',
    ]),
  );
  assert.equal(placement(draw, draft, 13, emptyBoard()).discards.length, 4);
});
test('variant capacity and share links', () => {
  assert.equal(capacity({ variant: 'classic' }), 4);
  assert.equal(capacity({ variant: 'pineapple' }), 3);
  assert.equal(capacity({ variant: 'classic', candyland: true }), 3);
  const data = { game: 'abc', invite: 'secret' };
  assert.deepEqual(
    invitation(
      `http://localhost/#join=${encodeURIComponent(JSON.stringify(data))}`,
    ),
    data,
  );
  assert.throws(() => invitation('http://localhost/#join=bad'));
});

test('the remaining pineapple card becomes a reversible proposed discard', () => {
  const draw = ['Ac', 'Kd', '2h'];
  const draft = { Ac: 'bottom', Kd: 'middle' };
  const proposed = proposeDiscards(draw, draft, 2);
  assert.equal(proposed['2h'], 'discard');
  assert.deepEqual(placement(draw, proposed, 2, emptyBoard()).discards, ['2h']);
  assert.deepEqual(draft, { Ac: 'bottom', Kd: 'middle' });
  assert.deepEqual(proposeDiscards(draw, { Ac: 'bottom' }, 2), {
    Ac: 'bottom',
  });
});

test('fantasyland proposes every remainder only once thirteen cards are placed', () => {
  const draw = Array.from({ length: 17 }, (_, i) => `c${i}`);
  const draft = Object.fromEntries(
    draw
      .slice(0, 13)
      .map((card, i) => [card, i < 3 ? 'top' : i < 8 ? 'middle' : 'bottom']),
  );
  assert.equal(
    placement(draw, proposeDiscards(draw, draft, 13), 13, emptyBoard()).discards
      .length,
    4,
  );
  assert.deepEqual(proposeDiscards(['Ac'], {}, 1), {});
});

test('retry identity survives unrelated turns but not a changed own action', () => {
  const game = {
    hand: {
      number: 3,
      status: 'playing',
      draws: { a: ['Ac', 'Kd'] },
      boards: { a: emptyBoard(), b: emptyBoard() },
      fantasy_pending: ['a'],
      turn: { player: 'b', keep: 2 },
    },
  };
  const identity = pendingAction(game);
  assert.ok(identity);
  game.hand.turn = null;
  game.hand.boards.b.top.push('2c');
  assert.equal(pendingAction(game), identity);
  game.hand.number++;
  assert.notEqual(pendingAction(game), identity);
  game.hand.number--;
  game.hand.fantasy_pending = [];
  assert.equal(pendingAction(game), null);
  game.hand.turn = { player: 'a', keep: 2 };
  const normal = pendingAction(game);
  game.hand.fantasy_pending = ['b'];
  assert.equal(pendingAction(game), normal);
  game.hand.boards.a.top.push('3c');
  assert.notEqual(pendingAction(game), normal);
  game.hand.status = 'complete';
  assert.equal(pendingAction(game), null);
});
