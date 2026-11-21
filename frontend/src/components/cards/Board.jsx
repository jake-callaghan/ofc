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
  preview,
  reveal = false,
  recovered = false,
  blockedRow,
}) {
  return (
    <div
      className={`board ${compact ? 'compact' : ''} ${reveal ? 'showdown-board' : ''} ${recovered ? 'board-recovered' : ''}`}
    >
      {Object.entries(ROWS).map(([row, size]) => {
        const placed = board[row] || [];
        const pending = Object.keys(draft).filter(
          (card) => draft[card] === row,
        );
        const slots = Math.max(0, size - placed.length - pending.length);
        return (
          <div
            className={`board-row ${preview?.invalidRows.includes(row) || blockedRow === row ? 'row-invalid' : ''}`}
            style={{ '--row-index': Object.keys(ROWS).indexOf(row) }}
            data-drop-row={editable && !hidden ? row : undefined}
            key={row}
          >
            <div className="row-label">
              <span>{row}</span>
              {preview?.labels[row] && (
                <small
                  className="royalty-preview"
                  key={`${preview.labels[row]}:${preview.royalties[row]}`}
                  aria-label={`${row}: ${preview.labels[row]}, ${preview.royalties[row]} provisional royalty units`}
                >
                  {preview.labels[row]} · +{preview.royalties[row]}
                </small>
              )}
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
                  onDrop={editable ? (row) => move(row, card) : undefined}
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
