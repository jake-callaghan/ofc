export const ROWS = { top: 3, middle: 5, bottom: 5 };
export const SUITS = { c: '♣', d: '♦', h: '♥', s: '♠' };
export const emptyBoard = () => ({ top: [], middle: [], bottom: [] });
export const units = (value = 0) => `${value > 0 ? '+' : ''}${value}`;
export const capacity = (rules) =>
  rules.variant === 'pineapple' || rules.candyland ? 3 : 4;

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

export function proposeDiscards(draw, draft, keep) {
  const placed = draw.filter((card) => draft[card] in ROWS).length;
  if (placed !== keep) return draft;

  // proposals are derived, so returning a placed card clears them immediately.
  return Object.fromEntries(
    draw.map((card) => [card, draft[card] || 'discard']),
  );
}

// identify the player's pending action so unrelated updates can be retried safely.
export function pendingAction(game) {
  const hand = game?.hand;
  if (!hand || hand.status !== 'playing') return null;
  const actor = Object.keys(hand.draws)[0];
  const draw = hand.draws[actor];
  const fantasy = hand.fantasy_pending?.includes(actor);
  if (!draw?.length || (!fantasy && hand.turn?.player !== actor)) return null;
  return JSON.stringify([
    hand.number,
    actor,
    draw,
    hand.boards[actor],
    fantasy ? 13 : hand.turn.keep,
  ]);
}
