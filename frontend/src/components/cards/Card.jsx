import { SUITS } from '../../lib/game.js';
export default function Card({
  card,
  selected,
  draft,
  onClick,
  small = false,
  ariaLabel,
}) {
  const red = card?.endsWith('h') || card?.endsWith('d');
  const rankLabel = card?.[0] === 'T' ? '10' : card?.[0];
  const suitSymbol = SUITS[card?.[1]];
  const suitName = { c: 'clubs', d: 'diamonds', h: 'hearts', s: 'spades' }[
    card?.[1]
  ];
  const draftHint = draft ? ', pending placement, click to return' : '';
  const accessibleLabel = `${rankLabel} of ${suitName}${draftHint}`;
  const cardClass = [
    'card',
    suitName && `suit-${suitName}`,
    red && 'red',
    selected && 'selected',
    draft && 'draft-card',
    small && 'small',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type="button"
      className={cardClass}
      disabled={!onClick}
      aria-label={ariaLabel || accessibleLabel}
      aria-pressed={onClick ? !!selected : undefined}
      onClick={onClick}
    >
      <span className="card-corner">
        {rankLabel}
        <i>{suitSymbol}</i>
      </span>
      <span className="card-suit">{suitSymbol}</span>
    </button>
  );
}
