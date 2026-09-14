import Board from '../../components/cards/Board.jsx';

export default function Opponents({ hand, names, playerId }) {
  return (
    <div className="opponents">
      {hand.players
        .filter((p) => p !== playerId)
        .map((p) => (
          <section
            className={`opponent ${hand.turn?.player === p ? 'is-turn' : ''}`}
            key={p}
          >
            <div className="opponent-heading">
              <strong>
                <span className="avatar">{names[p]?.[0]}</span>
                {names[p]}
              </strong>
              <span>
                {hand.turn?.player === p
                  ? '● Thinking'
                  : hand.fantasy[p]
                    ? '✦ Fantasyland'
                    : 'At the table'}
              </span>
            </div>
            <Board
              board={hand.boards[p]}
              compact
              hidden={!!hand.fantasy[p] && hand.status !== 'complete'}
            />
          </section>
        ))}
    </div>
  );
}
