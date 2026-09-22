export const ROWS = { top: 3, middle: 5, bottom: 5 };
export const SUITS = { c: '♣', d: '♦', h: '♥', s: '♠' };
export const emptyBoard = () => ({ top: [], middle: [], bottom: [] });
export const units = (value = 0) => `${value > 0 ? '+' : ''}${value}`;
export const capacity = (rules) =>
  rules.variant === 'pineapple' || rules.candyland ? 3 : 4;
export const rankOrder = '23456789TJQKA';
export const suitOrder = 'hcds';

export function assignCard(draft, card, destination, board) {
  const next = { ...draft };
  delete next[card];
  if (destination in ROWS) {
    const used =
      board[destination].length +
      Object.values(next).filter((r) => r === destination).length;
    if (used >= ROWS[destination]) return draft;
  }
  if (destination) next[card] = destination;
  return next;
}

export function placement(draw, draft, keep, board) {
  const placements = emptyBoard();
  const discards = [];
  if (Object.keys(draft).some((card) => !draw.includes(card))) return null;
  for (const card of draw) {
    const row = draft[card];
    if (row === 'discard') discards.push(card);
    else if (row in ROWS) placements[row].push(card);
    else return null;
  }
  if (draw.length - discards.length !== keep) return null;
  if (
    Object.entries(ROWS).some(
      ([row, size]) => board[row].length + placements[row].length > size,
    )
  )
    return null;
  return { type: 'place', placements, discards };
}

export function sortCardsByRank(cards) {
  return [...cards].sort((a, b) => {
    return rankOrder.indexOf(a[0]) - rankOrder.indexOf(b[0]);
  });
};

export function sortCardsBySuitAndRank(cards) {
  return [...cards].sort((a, b) => {
    const suitComparison = suitOrder.indexOf(a[1]) - suitOrder.indexOf(b[1]);
    if (suitComparison !== 0) {
      return suitComparison;
    }
    return rankOrder.indexOf(a[0]) - rankOrder.indexOf(b[0]);
  });
};

export function proposeDiscards(draw, draft, keep) {
  const placed = draw.filter((card) => draft[card] in ROWS).length;
  if (placed !== keep) return draft;

  // proposals are derived, so returning a placed card clears them immediately.
  return Object.fromEntries(
    draw.map((card) => [card, draft[card] || 'discard']),
  );
}
