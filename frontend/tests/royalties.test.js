import test from 'node:test';
import assert from 'node:assert/strict';
import {
  compareRanks,
  previewBoard,
  rankCards,
  rowRoyalty,
} from '../src/lib/royalties.js';

const cards = (text) => text.split(' ');
const board = (top, middle, bottom) => ({
  top: cards(top),
  middle: cards(middle),
  bottom: cards(bottom),
});

test('rank categories, wheel and kicker ordering agree with poker rules', () => {
  const hands = [
    'Ac Kd 9s 6h 2c',
    'Ac Ad 9s 6h 2c',
    'Ac Ad 9s 9h 2c',
    'Ac Ad As 6h 2c',
    'Ac 2d 3s 4h 5c',
    'Ac Jc 9c 6c 2c',
    'Ac Ad As 6h 6c',
    'Ac Ad As Ah 2c',
    'Tc Jc Qc Kc Ac',
  ];
  hands.forEach((hand, category) =>
    assert.equal(rankCards(cards(hand))[0], category),
  );
  assert.equal(rankCards(cards(hands[4]))[1], 5);
  assert.equal(
    compareRanks(
      rankCards(cards('2c 3d 4s 5h 6c')),
      rankCards(cards(hands[4])),
    ),
    1,
  );
  assert.equal(rankCards(cards('2c 3c 4c'))[0], 0);
  assert.equal(
    compareRanks(
      rankCards(cards('Qc Qd As')),
      rankCards(cards('Qh Qs Ac 3d 2c')),
    ),
    -1,
  );
  assert.equal(
    compareRanks(
      rankCards(cards('Qc Qd As')),
      rankCards(cards('Qh Qs Kc 3d 2c')),
    ),
    1,
  );
});

test('row royalties include top trips, middle trips and royal flushes', () => {
  assert.equal(rowRoyalty('top', rankCards(cards('Qc Qd As'))), 7);
  assert.equal(rowRoyalty('top', rankCards(cards('2c 2d 2s'))), 10);
  assert.equal(rowRoyalty('middle', rankCards(cards('Ac Ad As 6h 2c'))), 2);
  assert.equal(rowRoyalty('middle', rankCards(cards('Tc Jc Qc Kc Ac'))), 50);
  assert.equal(rowRoyalty('bottom', rankCards(cards('Tc Jc Qc Kc Ac'))), 25);
});

test('preview recognises the 14-unit fantasyland board from the screenshot', () => {
  const value = previewBoard(
    board('Jd Ts 8c', '2h 3h 4h 6h 7h', 'Kc Kd Ks 5s 5c'),
  );
  assert.equal(value.complete, true);
  assert.equal(value.foul, false);
  assert.equal(value.total, 14);
  assert.deepEqual(value.royalties, { top: 0, middle: 8, bottom: 6 });
});

test('only completed adjacent rows can foul, and a corrected draft becomes valid', () => {
  const initial = {
    top: cards('Ac Ad As'),
    middle: cards('2c 3d 4s 5h'),
    bottom: cards('7c 8c 9c Tc Jc'),
  };
  assert.equal(previewBoard(initial).foul, false);
  const foul = previewBoard(initial, { '9d': 'middle' });
  assert.equal(foul.foul, true);
  assert.deepEqual(foul.invalidRows, ['middle']);
  assert.equal(foul.total, 0);
  const fixed = previewBoard(
    board('2c 3d 4s', 'Ac Ad As 5h 9d', '7c 8c 9c Tc Jc'),
  );
  assert.equal(fixed.foul, false);
  assert.equal(fixed.total, 17);
});

test('candyland overrides normal fouls; moon requires all rows at most jack high', () => {
  const candy = board('Ac Kc Qc', '2d 4d 6d 8d Ad', '3h 5h 7h 9h Jh');
  assert.equal(previewBoard(candy).foul, true);
  assert.equal(previewBoard(candy, {}, { candyland: true }).foul, false);
  assert.equal(previewBoard(candy, {}, { candyland: true }).candyland, true);
  const moon = board('2c 4d 6h', '3c 5d 7h 8s 9c', '2h 4s 6c 8d Th');
  assert.equal(previewBoard(moon, {}, { moon: true }).moon, true);
  assert.equal(previewBoard(moon).moon, false);
});
