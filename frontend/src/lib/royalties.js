import { ROWS, rankOrder } from './game.js';

const categories = [
  'High card',
  'Pair',
  'Two pair',
  'Three of a kind',
  'Straight',
  'Flush',
  'Full house',
  'Four of a kind',
  'Straight flush',
];

// mirror the server's category and six-position kicker tuple, including top rows.
export function rankCards(cards) {
  if (![3, 5].includes(cards.length)) return null;
  const values = cards
    .map((card) => rankOrder.indexOf(card[0]) + 2)
    .sort((a, b) => b - a);
  const counts = new Map();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  const groups = [...counts]
    .map(([value, count]) => [count, value])
    .sort((a, b) => b[0] - a[0] || b[1] - a[1]);
  const ordered = groups.map(([, value]) => value);
  const unique = [...counts.keys()].sort((a, b) => a - b);
  const flush =
    cards.length === 5 && new Set(cards.map((card) => card[1])).size === 1;
  const straight =
    unique.length === 5
      ? unique[4] - unique[0] === 4
        ? unique[4]
        : unique.join(',') === '2,3,4,5,14'
          ? 5
          : 0
      : 0;
  let result;
  if (straight && flush) result = [8, straight];
  else if (groups[0][0] === 4) result = [7, ...ordered];
  else if (groups[0][0] === 3 && groups[1]?.[0] === 2) result = [6, ...ordered];
  else if (flush) result = [5, ...values];
  else if (straight) result = [4, straight];
  else if (groups[0][0] === 3) result = [3, ...ordered];
  else if (groups[0][0] === 2 && groups[1]?.[0] === 2) result = [2, ...ordered];
  else if (groups[0][0] === 2) result = [1, ...ordered];
  else result = [0, ...values];
  return [...result, ...Array(6 - result.length).fill(0)];
}

export function compareRanks(a, b) {
  for (let i = 0; i < 6; i++) if (a[i] !== b[i]) return Math.sign(a[i] - b[i]);
  return 0;
}

export function rowRoyalty(row, rank) {
  const [category, high] = rank;
  if (row === 'top')
    return category === 3
      ? high + 8
      : category === 1
        ? Math.max(0, high - 5)
        : 0;
  const base =
    { 4: 2, 5: 4, 6: 6, 7: 10, 8: high === 14 ? 25 : 15 }[category] || 0;
  return row === 'middle' ? (category === 3 ? 2 : base * 2) : base;
}

export function previewBoard(board, draft = {}, rules = {}) {
  const rows = Object.fromEntries(
    Object.keys(ROWS).map((row) => [
      row,
      [
        ...(board[row] || []),
        ...Object.keys(draft).filter((card) => draft[card] === row),
      ],
    ]),
  );
  const ranks = Object.fromEntries(
    Object.entries(ROWS).map(([row, size]) => [
      row,
      rows[row].length === size ? rankCards(rows[row]) : null,
    ]),
  );
  const complete = Object.values(ranks).every(Boolean);
  const candyland =
    complete &&
    !!rules.candyland &&
    Object.values(rows).every(
      (cards) => new Set(cards.map((card) => card[1])).size === 1,
    );
  const invalidRows = [];
  const reasons = [];
  // only compare completed adjacent rows; unfinished rows can still improve.
  if (!candyland) {
    for (const [stronger, weaker] of [
      ['middle', 'top'],
      ['bottom', 'middle'],
    ]) {
      if (
        ranks[stronger] &&
        ranks[weaker] &&
        compareRanks(ranks[stronger], ranks[weaker]) < 0
      ) {
        invalidRows.push(stronger);
        reasons.push(
          `${stronger === 'middle' ? 'Middle' : 'Bottom'} must be at least as strong as ${weaker}.`,
        );
      }
    }
  }
  const foul = invalidRows.length > 0;
  const moon =
    complete &&
    !!rules.moon &&
    !candyland &&
    !foul &&
    Object.values(ranks).every((rank) => rank[0] === 0 && rank[1] <= 11);
  const royalties = Object.fromEntries(
    Object.entries(ranks).map(([row, rank]) => [
      row,
      rank ? rowRoyalty(row, rank) : 0,
    ]),
  );
  return {
    rows,
    complete,
    foul,
    invalidRows,
    reasons,
    moon,
    candyland,
    royalties,
    total: foul
      ? 0
      : Object.values(royalties).reduce((sum, value) => sum + value, 0),
    labels: Object.fromEntries(
      Object.entries(ranks).map(([row, rank]) => [
        row,
        rank
          ? rank[0] === 8 && rank[1] === 14
            ? 'Royal flush'
            : categories[rank[0]]
          : null,
      ]),
    ),
  };
}
