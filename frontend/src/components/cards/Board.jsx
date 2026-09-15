import { ROWS, emptyBoard } from '../../lib/game.js';
import Card from './Card.jsx';
export default function Board({
  board = emptyBoard(),
  draft = {},
  editable,
  selected,
  move,
  remove,
  hidden,
  compact = false,
}) {
  return (
    <div className={`board ${compact ? 'compact' : ''}`}>
      {Object.entries(ROWS).map(([row, size]) => {
        const placed = board[row] || [];
        const pending = Object.keys(draft).filter(
          (card) => draft[card] === row,
        );
        const slots = Math.max(0, size - placed.length - pending.length);
        return (
          <div
            className="board-row"
            key={row}
          >
            <div className="row-label">
              <span>{row}</span>
            </div>
            <div className="row-cards">
              {placed.map((card) => (
                <Card
                  card={card}
                  key={card}
                  small={compact}
                />
              ))}
              {pending.map((card) => (
                <Card
                  card={card}
                  key={card}
                  small={compact}
                  draft
                  onClick={editable ? () => remove(card) : undefined}
                />
              ))}
              {Array.from({ length: slots }, (_, i) => (
                <button
                  type="button"
                  key={`slot-${i}`}
                  className={`slot ${hidden ? 'hidden-card' : ''} ${editable && selected ? 'available' : ''}`}
                  disabled={!editable || !selected || hidden}
                  onClick={() => move(row)}
                  aria-label={`Place selected card in ${row}`}
                >
                  {hidden ? '✦' : editable && selected ? '+' : <span>·</span>}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
